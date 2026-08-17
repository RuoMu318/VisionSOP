# P0 API Server

The service exposes the deterministic SOP runtime through REST and WebSocket APIs. Runtime Bundle `ST01-P0-R02` is camera-only and currently uses simulated camera/vision adapters; it does not perform real image inference. PostgreSQL is selected by setting `DATABASE_URL`, otherwise SQLite is used.

```powershell
$env:SOP_DATA_DIR = "data"
.\.venv\Scripts\python.exe -m uvicorn sop_api.main:app --app-dir services/api-server --host 127.0.0.1 --port 8000
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. P0 intentionally has no `ENFORCING` runtime mode.

## USB Camera Development Mode

Windows development can preview the detected USB camera through OpenCV. This runtime only exposes live video, JPEG snapshots, MJPEG streaming, and camera health; it does not generate visual SOP evidence or run an AI model.

```powershell
$env:CAMERA_MODE = "USB"
$env:CAMERA_INDEX = "0"
$env:CAMERA_WIDTH = "1280"
$env:CAMERA_HEIGHT = "720"
$env:CAMERA_FPS = "15"
.\.venv\Scripts\python.exe -m uvicorn sop_api.main:app --app-dir services/api-server --host 127.0.0.1 --port 8000
```

The station preview uses `/api/v1/cameras/ST01/stream.mjpg`; a current frame is available from `/api/v1/cameras/ST01/snapshot.jpg`. If the camera cannot provide a frame, the API returns `503` and the station reports `CAMERA_UNAVAILABLE` behavior rather than creating simulated video or SOP evidence.
