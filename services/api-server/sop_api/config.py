"""Environment-backed configuration with software-only P0 defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from core_runtime import RuntimeMode


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    runtime_mode: RuntimeMode
    station_id: str = "ST01"
    station_name: str = "装配工位 01"
    event_lateness_seconds: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.getenv("SOP_DATA_DIR", "data")).resolve()
        database_url = os.getenv("DATABASE_URL", f"sqlite:///{(root / 'sop-p0.db').as_posix()}")
        mode = RuntimeMode(os.getenv("RUNTIME_MODE", RuntimeMode.SIMULATION.value))
        return cls(
            database_url=database_url,
            data_dir=root,
            runtime_mode=mode,
            station_id=os.getenv("STATION_ID", "ST01"),
            station_name=os.getenv("STATION_NAME", "装配工位 01"),
            event_lateness_seconds=int(os.getenv("EVENT_LATENESS_SECONDS", "5")),
        )
