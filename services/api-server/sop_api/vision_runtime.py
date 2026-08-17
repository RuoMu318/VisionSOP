"""Generic execution primitives for published Vision Recipes.

Only CLASSICAL_CV is implemented locally today. Object detection,
classification, segmentation and action recipes deliberately report their
model as unavailable until an approved model adapter is deployed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Callable, Protocol

from .vision import RecipeStatus, RecognizerType, VisionRecipe


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
        if recipe.recognizer.type != RecognizerType.CLASSICAL_CV:
            return VisionEvaluation("MODEL_NOT_DEPLOYED", False, False, None, 0, 0,
                                    detail="the selected recognizer has no deployed runtime adapter")
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

    def _apply_temporal_filter(self, recipe: VisionRecipe, candidate: bool, confidence: float) -> VisionEvaluation:
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
        payload = self._event_payload(recipe, confidence) if confirmed else None
        return VisionEvaluation(
            "OK", candidate, confirmed, round(confidence, 4), state.stable_frames, state.lost_frames,
            event_payload=payload,
        )

    @staticmethod
    def _event_payload(recipe: VisionRecipe, confidence: float) -> dict:
        return {
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
        if any(recipe.recognizer.type != RecognizerType.CLASSICAL_CV for recipe in published):
            return "MODEL_NOT_DEPLOYED"
        if any(not self.runtime._reference_path(recipe).exists() for recipe in published):
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
