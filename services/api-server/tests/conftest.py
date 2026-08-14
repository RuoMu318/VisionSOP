from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "services" / "core-runtime"
API = ROOT / "services" / "api-server"
sys.path[:0] = [str(CORE), str(API)]

from core_runtime import RuntimeMode  # noqa: E402
from sop_api import create_app  # noqa: E402
from sop_api.config import Settings  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'p0.db').as_posix()}",
        data_dir=tmp_path / "data",
        runtime_mode=RuntimeMode.SIMULATION,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
