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
    camera_mode: str = "SIMULATED"
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 15

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
            camera_mode=os.getenv("CAMERA_MODE", "SIMULATED").upper(),
            camera_index=int(os.getenv("CAMERA_INDEX", "0")),
            camera_width=int(os.getenv("CAMERA_WIDTH", "1280")),
            camera_height=int(os.getenv("CAMERA_HEIGHT", "720")),
            camera_fps=int(os.getenv("CAMERA_FPS", "15")),
        )
