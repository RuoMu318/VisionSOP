"""Write-side API contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from core_runtime import Disposition


class DispositionRequest(BaseModel):
    disposition: Disposition
    actor_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def reject_none(self) -> "DispositionRequest":
        if self.disposition == Disposition.NONE:
            raise ValueError("NONE is not a valid disposition command")
        return self


class AcknowledgeRequest(BaseModel):
    actor_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ResetRequest(BaseModel):
    actor_id: str = Field(default="simulation-operator", min_length=1)
