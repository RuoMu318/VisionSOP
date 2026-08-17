"""Versioned, configuration-driven vision recipes.

Recipes describe how a generic recognizer is applied at one station. They do
not contain product-specific inference code and are deliberately independent
from the SOP rule engine.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecognizerType(StrEnum):
    CLASSICAL_CV = "CLASSICAL_CV"
    OBJECT_DETECTION = "OBJECT_DETECTION"
    CLASSIFICATION = "CLASSIFICATION"
    SEGMENTATION = "SEGMENTATION"
    ACTION = "ACTION"


class RecipeStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class SpatialRule(StrEnum):
    CENTER_INSIDE_ROI = "CENTER_INSIDE_ROI"
    INTERSECTS_ROI = "INTERSECTS_ROI"
    COUNT_AT_LEAST = "COUNT_AT_LEAST"


class Roi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{2,63}$")
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class RecognizerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: RecognizerType
    model_id: str | None = Field(default=None, max_length=96)
    target_class: str | None = Field(default=None, max_length=96)

    @model_validator(mode="after")
    def inference_recognizers_need_a_model(self) -> "RecognizerConfig":
        if self.type in {
            RecognizerType.OBJECT_DETECTION,
            RecognizerType.CLASSIFICATION,
            RecognizerType.SEGMENTATION,
            RecognizerType.ACTION,
        } and not self.model_id:
            raise ValueError(f"{self.type} requires a deployed model_id")
        if self.type == RecognizerType.OBJECT_DETECTION and not self.target_class:
            raise ValueError("OBJECT_DETECTION requires target_class")
        return self


class RecognitionCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence_min: float = Field(ge=0, le=1)
    count_min: int = Field(default=1, ge=1)
    change_min: float | None = Field(default=None, ge=0, le=1)


class TemporalFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_frames: int = Field(ge=1, le=600)
    lost_frames: int = Field(ge=1, le=600)
    cooldown_ms: int = Field(ge=0, le=60_000)


class EventOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(default="OBJECT_STATE_CONFIRMED", pattern=r"^[A-Z_]{3,64}$")
    state: str = Field(pattern=r"^[a-z][a-z0-9_]{2,95}$")

    @model_validator(mode="after")
    def output_is_a_state_event(self) -> "EventOutput":
        if self.event_type != "OBJECT_STATE_CONFIRMED":
            raise ValueError("V1 state recipes may only emit OBJECT_STATE_CONFIRMED")
        return self


class SopBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sop_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{2,95}$")
    step_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")
    evidence_key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,95}$")


class VisionRecipeDraft(BaseModel):
    """Editable recipe contents. Coordinates always use the camera's raw pixels."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,95}$")
    name: str = Field(min_length=3, max_length=128)
    station_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")
    camera_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")
    recognizer: RecognizerConfig
    roi: Roi
    condition: RecognitionCondition
    spatial_rule: SpatialRule = SpatialRule.CENTER_INSIDE_ROI
    temporal: TemporalFilter
    output: EventOutput
    sop_binding: SopBinding

    @model_validator(mode="after")
    def output_must_match_bound_evidence(self) -> "VisionRecipeDraft":
        if self.output.state != self.sop_binding.evidence_key:
            raise ValueError("output.state must match sop_binding.evidence_key")
        if self.recognizer.type == RecognizerType.CLASSICAL_CV and self.condition.change_min is None:
            raise ValueError("CLASSICAL_CV requires condition.change_min")
        return self


class VisionRecipe(VisionRecipeDraft):
    version: int = Field(ge=1)
    status: RecipeStatus


class VisionModelView(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    name: str
    framework: str
    recognizer_types: tuple[RecognizerType, ...]
    classes: tuple[str, ...] = ()
    deployment_status: str


BUILT_IN_MODELS = (
    VisionModelView(
        model_id="fixture-occupancy-cv-v1",
        name="Fixture occupancy CV baseline",
        framework="OpenCV",
        recognizer_types=(RecognizerType.CLASSICAL_CV,),
        deployment_status="BUILT_IN",
    ),
    VisionModelView(
        model_id="ultralytics-yolo11n-coco-v1",
        name="YOLO11n COCO object detector",
        framework="Ultralytics YOLO11",
        recognizer_types=(RecognizerType.OBJECT_DETECTION,),
        classes=(
            "person", "bicycle", "car", "motorcycle", "bus", "truck", "bottle", "cup",
            "fork", "knife", "spoon", "scissors", "cell phone", "backpack", "handbag",
        ),
        deployment_status="INSTALLED_LOCAL_CPU",
    ),
)
