# P0 API Server

The service exposes the deterministic SOP runtime through REST and WebSocket APIs. Runtime Bundle `ST01-P0-R03` is camera-only and adds a versioned Vision Recipe Engine. PostgreSQL is selected by setting `DATABASE_URL`, otherwise SQLite is used.

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

## Vision Recipe Engine

`Vision Recipe` separates a recognizer/model from its station-specific ROI, threshold, temporal filter, output event, and SOP Evidence binding. Recipes are created as drafts, tested, and published as immutable versions. The API rejects a recipe unless its output is an existing required `STATE` Evidence on the bound SOP step.

```text
GET  /api/v1/vision/models
GET  /api/v1/vision/recipes
POST /api/v1/vision/recipes
PUT  /api/v1/vision/recipes/{template_id}
POST /api/v1/vision/recipes/{template_id}/draft
POST /api/v1/vision/recipes/{template_id}/calibration
POST /api/v1/vision/recipes/{template_id}/test
POST /api/v1/vision/recipes/{template_id}/publish
```

The built-in `fixture-occupancy-cv-v1` is a generic OpenCV background-difference baseline for a fixed scene. It only produces a candidate after an empty-scene reference has been captured and the configured temporal filter is satisfied. Object detection, classification, segmentation, and action recipes remain `MODEL_NOT_DEPLOYED` until an approved model adapter is installed; no synthetic Vision Event is created in that state.
