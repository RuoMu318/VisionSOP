# P0 API Server

The service exposes the deterministic SOP runtime through REST and WebSocket APIs. It defaults to SQLite and simulated adapters; PostgreSQL is selected by setting `DATABASE_URL`.

```powershell
$env:SOP_DATA_DIR = "data"
.\.venv\Scripts\python.exe -m uvicorn sop_api.main:app --app-dir services/api-server --host 127.0.0.1 --port 8000
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. P0 intentionally has no `ENFORCING` runtime mode.
