"""Generic execution primitives for published Vision Recipes.

Only CLASSICAL_CV is implemented locally today. Object detection,
classification, segmentation and action recipes deliberately report their
model as unavailable until an approved model adapter is deployed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
from typing import Any, Callable, Protocol

from .vision import RecipeStatus, RecognizerType, SpatialRule, VisionRecipe


@dataclass(frozen=True)
class CalibrationResult:
    status: str
    reference_path: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class VisionEvaluation:
    status: str
    candidate: bool
    confirmed: bool
    confidence: float | None
    stable_frames: int
    lost_frames: int
    event_payload: dict | None = None
    detail: str | None = None


@dataclass
class _TemporalState:
    stable_frames: int = 0
    lost_frames: int = 0
    last_emitted_at: datetime | None = None


class VisionRecipeRuntime:
    """Executes the common parts of every recipe without SOP-specific code."""

    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        self.calibration_dir = self.data_dir / "vision" / "calibrations"
        self._state: dict[tuple[str, int], _TemporalState] = {}
        self._models: dict[str, Any] = {}
        self.device = os.getenv("VISION_DEVICE", "cpu")

    def calibrate(self, recipe: VisionRecipe, jpeg: bytes | None) -> CalibrationResult:
        if jpeg is None:
            return CalibrationResult("CAMERA_UNAVAILABLE", detail="camera did not provide a frame")
        if recipe.recognizer.type != RecognizerType.CLASSICAL_CV:
            return CalibrationResult("NOT_SUPPORTED", detail="only CLASSICAL_CV recipes use an image reference")
        frame = self._decode(jpeg)
        if frame is None:
            return CalibrationResult("INVALID_FRAME", detail="camera frame cannot be decoded")
        roi = self._crop(frame, recipe)
        if roi is None:
            return CalibrationResult("ROI_OUT_OF_FRAME", detail="recipe ROI does not fit the current camera frame")
        import cv2

        path = self._reference_path(recipe)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), roi):
            return CalibrationResult("PERSISTENCE_FAILED", detail="reference image cannot be written")
        self._state.pop(self._state_key(recipe), None)
        return CalibrationResult("CALIBRATED", reference_path=str(path))

    def evaluate(self, recipe: VisionRecipe, jpeg: bytes | None) -> VisionEvaluation:
        if jpeg is None:
            return VisionEvaluation("CAMERA_UNAVAILABLE", False, False, None, 0, 0)
        if recipe.recognizer.type == RecognizerType.OBJECT_DETECTION:
            frame = self._decode(jpeg)
            if frame is None:
                return VisionEvaluation("INVALID_FRAME", False, False, None, 0, 0)
            return self._evaluate_object_detection(recipe, frame)
        if recipe.recognizer.type != RecognizerType.CLASSICAL_CV:
            return VisionEvaluation(
                "MODEL_NOT_DEPLOYED", False, False, None, 0, 0,
                detail="the selected recognizer has no deployed runtime adapter",
            )
        reference_path = self._reference_path(recipe)
        if not reference_path.exists():
            return VisionEvaluation("CALIBRATION_REQUIRED", False, False, None, 0, 0,
                                    detail="capture an empty-scene reference for this published recipe version")
        frame = self._decode(jpeg)
        if frame is None:
            return VisionEvaluation("INVALID_FRAME", False, False, None, 0, 0)
        roi = self._crop(frame, recipe)
        if roi is None:
            return VisionEvaluation("ROI_OUT_OF_FRAME", False, False, None, 0, 0)

        import cv2
        import numpy as np

        reference = cv2.imread(str(reference_path), cv2.IMREAD_GRAYSCALE)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if reference is None or reference.shape != gray.shape:
            return VisionEvaluation("CALIBRATION_INVALID", False, False, None, 0, 0,
                                    detail="reference dimensions do not match the current ROI")
        difference = cv2.absdiff(gray, reference)
        changed_ratio = float(np.count_nonzero(difference >= 25)) / float(difference.size)
        threshold = recipe.condition.change_min or 1.0
        confidence = min(1.0, changed_ratio / threshold)
        candidate = changed_ratio >= threshold and confidence >= recipe.condition.confidence_min
        return self._apply_temporal_filter(recipe, candidate, confidence)

    def model_status(self, recipe: VisionRecipe) -> str:
        """Return the concrete runtime state without generating a Vision Event."""
        if recipe.recognizer.type == RecognizerType.CLASSICAL_CV:
            return "READY" if self._reference_path(recipe).exists() else "CALIBRATION_REQUIRED"
        if recipe.recognizer.type == RecognizerType.OBJECT_DETECTION:
            if not self._supports_model(recipe):
                return "MODEL_NOT_DEPLOYED"
            return "READY" if self._model_path(recipe) is not None else "MODEL_WEIGHTS_REQUIRED"
        return "MODEL_NOT_DEPLOYED"

    def _evaluate_object_detection(self, recipe: VisionRecipe, frame) -> VisionEvaluation:
        if not self._supports_model(recipe):
            return VisionEvaluation(
                "MODEL_NOT_DEPLOYED", False, False, None, 0, 0,
                detail="the selected model has no deployed runtime adapter",
            )
        model_path = self._model_path(recipe)
        if model_path is None:
            return VisionEvaluation(
                "MODEL_WEIGHTS_REQUIRED", False, False, None, 0, 0,
                detail="install an approved local model weight before publishing this recipe",
            )
        try:
            model = self._models.get(recipe.recognizer.model_id or "")
            if model is None:
                from ultralytics import YOLO

                model = YOLO(str(model_path))
                self._models[recipe.recognizer.model_id or ""] = model
            result = model.predict(
                source=frame,
                conf=recipe.condition.confidence_min,
                verbose=False,
                device=self.device,
            )[0]
        except ImportError:
            return VisionEvaluation(
                "MODEL_RUNTIME_UNAVAILABLE", False, False, None, 0, 0,
                detail="Ultralytics runtime is not installed",
            )
        except Exception as error:  # Model failures are observable; they never become Evidence.
            return VisionEvaluation("MODEL_INFERENCE_FAILED", False, False, None, 0, 0, detail=str(error))

        target = recipe.recognizer.target_class or ""
        matching: list[float] = []
        if result.boxes is not None:
            names = result.names
            for box in result.boxes:
                class_id = int(box.cls.item())
                class_name = str(names[class_id])
                confidence = float(box.conf.item())
                coordinates = [float(value) for value in box.xyxy[0].tolist()]
                if class_name != target or not self._matches_spatial_rule(recipe, coordinates):
                    continue
                matching.append(confidence)

        count = len(matching)
        confidence = max(matching, default=0.0)
        candidate = count >= recipe.condition.count_min
        return self._apply_temporal_filter(
            recipe,
            candidate,
            confidence,
            metadata={"target_class": target, "detection_count": count, "device": self.device},
        )

    @staticmethod
    def _matches_spatial_rule(recipe: VisionRecipe, coordinates: list[float]) -> bool:
        left, top, right, bottom = coordinates
        roi_left, roi_top = recipe.roi.x, recipe.roi.y
        roi_right, roi_bottom = roi_left + recipe.roi.width, roi_top + recipe.roi.height
        if recipe.spatial_rule in {SpatialRule.CENTER_INSIDE_ROI, SpatialRule.COUNT_AT_LEAST}:
            center_x, center_y = (left + right) / 2, (top + bottom) / 2
            return roi_left <= center_x <= roi_right and roi_top <= center_y <= roi_bottom
        return not (right < roi_left or left > roi_right or bottom < roi_top or top > roi_bottom)

    def _apply_temporal_filter(
        self,
        recipe: VisionRecipe,
        candidate: bool,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> VisionEvaluation:
        state = self._state.setdefault(self._state_key(recipe), _TemporalState())
        if candidate:
            state.stable_frames += 1
            state.lost_frames = 0
        else:
            state.lost_frames += 1
            if state.lost_frames >= recipe.temporal.lost_frames:
                state.stable_frames = 0
        now = datetime.now(timezone.utc)
        ready = state.stable_frames >= recipe.temporal.confirm_frames
        cooldown_elapsed = (
            state.last_emitted_at is None
            or (now - state.last_emitted_at).total_seconds() * 1000 >= recipe.temporal.cooldown_ms
        )
        confirmed = ready and cooldown_elapsed
        if confirmed:
            state.last_emitted_at = now
        payload = self._event_payload(recipe, confidence, metadata) if confirmed else None
        return VisionEvaluation(
            "OK", candidate, confirmed, round(confidence, 4), state.stable_frames, state.lost_frames,
            event_payload=payload,
        )

    @staticmethod
    def _event_payload(recipe: VisionRecipe, confidence: float, metadata: dict[str, Any] | None = None) -> dict:
        payload = {
            "state": recipe.output.state,
            "value": True,
            "confidence": round(confidence, 4),
            "model_version": recipe.recognizer.model_id,
            "valid_for_seconds": 30,
            "recipe_id": recipe.template_id,
            "recipe_version": recipe.version,
            "roi_id": recipe.roi.id,
            "recognizer_type": recipe.recognizer.type.value,
        }
        if metadata:
            payload.update(metadata)
        return payload

    def _model_path(self, recipe: VisionRecipe) -> Path | None:
        path = self.data_dir / "models" / "ultralytics" / "yolo11n.pt"
        return path if path.exists() else None

    @staticmethod
    def _supports_model(recipe: VisionRecipe) -> bool:
        return recipe.recognizer.model_id == "ultralytics-yolo11n-coco-v1"

    @staticmethod
    def _decode(jpeg: bytes):
        import cv2
        import numpy as np

        return cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)

    @staticmethod
    def _crop(frame, recipe: VisionRecipe):
        x, y = recipe.roi.x, recipe.roi.y
        end_x, end_y = x + recipe.roi.width, y + recipe.roi.height
        height, width = frame.shape[:2]
        if end_x > width or end_y > height:
            return None
        return frame[y:end_y, x:end_x]

    def _reference_path(self, recipe: VisionRecipe) -> Path:
        return self.calibration_dir / recipe.template_id / f"v{recipe.version}-{recipe.roi.id}.png"

    @staticmethod
    def _state_key(recipe: VisionRecipe) -> tuple[str, int]:
        return recipe.template_id, recipe.version


class _FrameSource(Protocol):
    def snapshot_jpeg(self) -> bytes | None: ...


class _RecipeSource(Protocol):
    def vision_recipes(self, station_id: str | None = None) -> list[VisionRecipe]: ...


class VisionRecipeWorker:
    """Poll published recipes and emit only confirmed generic state outputs."""

    def __init__(
        self,
        station_id: str,
        camera: _FrameSource,
        recipes: _RecipeSource,
        runtime: VisionRecipeRuntime,
        on_confirmation: Callable[[VisionRecipe, dict], bool],
        poll_interval_ms: int = 250,
    ) -> None:
        self.station_id = station_id
        self.camera = camera
        self.recipes = recipes
        self.runtime = runtime
        self.on_confirmation = on_confirmation
        self.poll_interval_seconds = max(poll_interval_ms, 50) / 1000
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_results: dict[tuple[str, int], VisionEvaluation] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="vision-recipe-runtime", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def health(self) -> str:
        published = self._published_recipes()
        if not published:
            return "NO_PUBLISHED_RECIPE"
        statuses = {self.runtime.model_status(recipe) for recipe in published}
        if "MODEL_NOT_DEPLOYED" in statuses:
            return "MODEL_NOT_DEPLOYED"
        if "MODEL_WEIGHTS_REQUIRED" in statuses:
            return "MODEL_WEIGHTS_REQUIRED"
        if "CALIBRATION_REQUIRED" in statuses:
            return "CALIBRATION_REQUIRED"
        return "READY"

    def last_result(self, recipe: VisionRecipe) -> VisionEvaluation | None:
        return self._last_results.get((recipe.template_id, recipe.version))

    def _published_recipes(self) -> list[VisionRecipe]:
        return [
            item for item in self.recipes.vision_recipes(self.station_id)
            if item.status == RecipeStatus.PUBLISHED
        ]

    def _run(self) -> None:
        while not self._stop.is_set():
            recipes = self._published_recipes()
            if recipes:
                frame = self.camera.snapshot_jpeg()
                for recipe in recipes:
                    result = self.runtime.evaluate(recipe, frame)
                    self._last_results[(recipe.template_id, recipe.version)] = result
                    if result.confirmed and result.event_payload:
                        self.on_confirmation(recipe, result.event_payload)
            self._stop.wait(self.poll_interval_seconds)
