from __future__ import annotations

import cv2
import numpy as np

from sop_api.vision import (
    EventOutput,
    RecognitionCondition,
    RecognizerConfig,
    RecognizerType,
    Roi,
    SopBinding,
    SpatialRule,
    TemporalFilter,
    VisionRecipe,
)
from sop_api.vision_runtime import VisionRecipeRuntime


def recipe() -> VisionRecipe:
    return VisionRecipe(
        template_id="fixture_presence", version=1, status="PUBLISHED", name="Fixture presence",
        station_id="ST01", camera_id="ST01_CAM01",
        recognizer=RecognizerConfig(type=RecognizerType.CLASSICAL_CV, model_id="fixture-occupancy-cv-v1"),
        roi=Roi(id="fixture_roi", x=20, y=20, width=80, height=60),
        condition=RecognitionCondition(confidence_min=0.8, change_min=0.1),
        spatial_rule=SpatialRule.CENTER_INSIDE_ROI,
        temporal=TemporalFilter(confirm_frames=3, lost_frames=5, cooldown_ms=0),
        output=EventOutput(state="fixture_present"),
        sop_binding=SopBinding(sop_id="SOP_001", step_id="S02", evidence_key="fixture_present"),
    )


def jpeg(frame: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame)
    assert ok
    return encoded.tobytes()


def test_classical_cv_recipe_uses_calibrated_roi_and_temporal_filter(tmp_path):
    runtime = VisionRecipeRuntime(tmp_path)
    configured = recipe()
    empty = np.zeros((120, 160, 3), dtype=np.uint8)
    occupied = empty.copy()
    occupied[20:80, 20:100] = 255

    calibration = runtime.calibrate(configured, jpeg(empty))
    assert calibration.status == "CALIBRATED"

    first = runtime.evaluate(configured, jpeg(occupied))
    second = runtime.evaluate(configured, jpeg(occupied))
    third = runtime.evaluate(configured, jpeg(occupied))

    assert first.candidate is True
    assert first.stable_frames == 1
    assert second.confirmed is False
    assert third.confirmed is True
    assert third.confidence == 1.0
    assert third.event_payload == {
        "state": "fixture_present",
        "value": True,
        "confidence": 1.0,
        "model_version": "fixture-occupancy-cv-v1",
        "valid_for_seconds": 30,
        "recipe_id": "fixture_presence",
        "recipe_version": 1,
        "roi_id": "fixture_roi",
        "recognizer_type": "CLASSICAL_CV",
    }


def test_unconfigured_detector_recipe_never_claims_a_result(tmp_path):
    runtime = VisionRecipeRuntime(tmp_path)
    configured = recipe().model_copy(update={
        "recognizer": RecognizerConfig(
            type=RecognizerType.OBJECT_DETECTION, model_id="product_detector_v1", target_class="product",
        ),
    })
    frame = jpeg(np.zeros((120, 160, 3), dtype=np.uint8))

    result = runtime.evaluate(configured, frame)

    assert result.status == "MODEL_NOT_DEPLOYED"
    assert result.confirmed is False
    assert result.event_payload is None
