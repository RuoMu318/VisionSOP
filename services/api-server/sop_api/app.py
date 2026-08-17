"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager

from core_runtime import DispositionCommand
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from .camera import CameraRuntime, create_camera_runtime
from .config import Settings
from .db import create_schema, create_session_factory
from .orchestrator import SCENARIOS, StationOrchestrator
from .repository import Repository
from .schemas import AcknowledgeRequest, DispositionRequest, ResetRequest
from .vision import BUILT_IN_MODELS, VisionRecipeDraft
from .vision_runtime import VisionRecipeRuntime, VisionRecipeWorker


def create_app(
    settings: Settings | None = None,
    camera_factory: Callable[[Settings], CameraRuntime] | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    resolved.data_dir.mkdir(parents=True, exist_ok=True)
    factory = create_session_factory(resolved.database_url)
    create_schema(factory)
    repository = Repository(factory)
    camera: CameraRuntime = (camera_factory or create_camera_runtime)(resolved)
    vision_runtime = VisionRecipeRuntime(resolved.data_dir)
    vision_worker: VisionRecipeWorker | None = None

    def vision_health() -> str:
        return vision_worker.health() if vision_worker else "INITIALIZING"

    orchestrator = StationOrchestrator(resolved, repository, camera, vision_health=vision_health)
    vision_worker = VisionRecipeWorker(
        resolved.station_id, camera, repository, vision_runtime, orchestrator.ingest_vision_confirmation,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        camera.start()
        vision_worker.start()
        try:
            yield
        finally:
            vision_worker.close()
            camera.close()

    app = FastAPI(
        title="AI Production SOP Compliance Platform",
        version="0.1.0-p0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.settings = resolved
    app.state.repository = repository
    app.state.orchestrator = orchestrator
    app.state.camera = camera
    app.state.vision_runtime = vision_runtime
    app.state.vision_worker = vision_worker

    def validate_recipe_binding(recipe: VisionRecipeDraft) -> None:
        if recipe.station_id != resolved.station_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "recipe station_id is not configured")
        if recipe.sop_binding.sop_id != orchestrator.sop.sop_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "recipe is bound to an unknown SOP")
        step = next((item for item in orchestrator.sop.steps if item.step_id == recipe.sop_binding.step_id), None)
        if step is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "recipe is bound to an unknown SOP step")
        if not any(
            item.key == recipe.sop_binding.evidence_key and item.kind.value == "STATE"
            for item in step.required
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "recipe output is not a required STATE Evidence for the bound SOP step",
            )

    @app.get("/api/v1/health")
    def health() -> dict:
        return {
            "status": "ok", "version": app.version, "mode": resolved.runtime_mode.value,
            "database": "sqlite" if resolved.database_url.startswith("sqlite") else "postgresql",
            "hardware": camera.adapter_name,
        }

    @app.get("/api/v1/stations")
    def stations() -> list[dict]:
        return orchestrator.stations()

    @app.get("/api/v1/stations/{station_id}/snapshot")
    def station_snapshot(station_id: str) -> dict:
        try:
            return orchestrator.station_snapshot(station_id)
        except LookupError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "station not found") from error

    @app.get("/api/v1/cycles")
    def cycles(serial_number: str | None = Query(default=None)) -> list[dict]:
        return orchestrator.cycles(serial_number)

    @app.get("/api/v1/cycles/{cycle_id}")
    def cycle_detail(cycle_id: str) -> dict:
        try:
            return orchestrator.cycle_detail(cycle_id)
        except LookupError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "cycle not found") from error

    @app.post("/api/v1/cycles/{cycle_id}/dispositions")
    async def disposition(cycle_id: str, request: DispositionRequest) -> dict:
        command = DispositionCommand(cycle_id=cycle_id, **request.model_dump())
        try:
            result = orchestrator.apply_disposition(cycle_id, command)
        except LookupError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "cycle not found") from error
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        await orchestrator.publish(orchestrator.station_snapshot(resolved.station_id))
        return result

    @app.get("/api/v1/alarms")
    def alarms(
        domain: str | None = Query(default=None, pattern="^(PROCESS|SYSTEM)$"),
        acknowledged: bool | None = Query(default=None),
    ) -> list[dict]:
        return [orchestrator._alarm_view(item) for item in repository.alarm_rows(domain, acknowledged)]

    @app.post("/api/v1/alarms/{alarm_id}/acknowledge")
    async def acknowledge(alarm_id: str, request: AcknowledgeRequest) -> dict:
        row = repository.acknowledge_alarm(alarm_id, **request.model_dump())
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "alarm not found")
        await orchestrator.publish(orchestrator.station_snapshot(resolved.station_id))
        return orchestrator._alarm_view(row)

    @app.get("/api/v1/evidence/{asset_id}")
    def evidence(asset_id: str) -> dict:
        row = repository.evidence_asset(asset_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "evidence asset not found")
        return orchestrator._asset_view(row)

    @app.get("/api/v1/vision/models")
    def vision_models() -> list[dict]:
        return [item.model_dump(mode="json") for item in BUILT_IN_MODELS]

    @app.get("/api/v1/vision/recipes")
    def vision_recipes(station_id: str | None = Query(default=None)) -> list[dict]:
        return [item.model_dump(mode="json") for item in repository.vision_recipes(station_id)]

    @app.post("/api/v1/vision/recipes", status_code=status.HTTP_201_CREATED)
    def create_vision_recipe(recipe: VisionRecipeDraft) -> dict:
        validate_recipe_binding(recipe)
        try:
            return repository.create_vision_recipe(recipe).model_dump(mode="json")
        except ValueError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    @app.put("/api/v1/vision/recipes/{template_id}")
    def update_vision_recipe(template_id: str, recipe: VisionRecipeDraft) -> dict:
        validate_recipe_binding(recipe)
        try:
            return repository.update_vision_recipe(template_id, recipe).model_dump(mode="json")
        except ValueError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    @app.post("/api/v1/vision/recipes/{template_id}/draft", status_code=status.HTTP_201_CREATED)
    def create_vision_draft(template_id: str) -> dict:
        try:
            return repository.create_vision_draft(template_id).model_dump(mode="json")
        except LookupError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "vision recipe not found") from error
        except ValueError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    @app.post("/api/v1/vision/recipes/{template_id}/publish")
    def publish_vision_recipe(template_id: str) -> dict:
        try:
            return repository.publish_vision_recipe(template_id).model_dump(mode="json")
        except ValueError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    @app.post("/api/v1/vision/recipes/{template_id}/calibration")
    def calibrate_vision_recipe(template_id: str, version: int | None = Query(default=None, ge=1)) -> dict:
        recipe = repository.vision_recipe(template_id, version)
        if recipe is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "vision recipe not found")
        result = vision_runtime.calibrate(recipe, camera.snapshot_jpeg())
        return {"recipe": recipe.model_dump(mode="json"), "calibration": result.__dict__}

    @app.post("/api/v1/vision/recipes/{template_id}/test")
    def test_vision_recipe(template_id: str, version: int | None = Query(default=None, ge=1)) -> dict:
        recipe = repository.vision_recipe(template_id, version)
        if recipe is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "vision recipe not found")
        result = vision_runtime.evaluate(recipe, camera.snapshot_jpeg())
        return {"recipe": recipe.model_dump(mode="json"), "result": result.__dict__}

    @app.get("/api/v1/cameras/{station_id}/snapshot.jpg")
    def camera_snapshot(station_id: str) -> Response:
        if station_id != resolved.station_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "station not found")
        jpeg = camera.snapshot_jpeg()
        if jpeg is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "camera frame unavailable")
        return Response(content=jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/cameras/{station_id}/stream.mjpg")
    def camera_stream(station_id: str) -> StreamingResponse:
        if station_id != resolved.station_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "station not found")
        if camera.snapshot_jpeg() is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "camera frame unavailable")
        return StreamingResponse(
            camera.mjpeg(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/sops/{sop_id}/versions/{version}")
    def sop_version(sop_id: str, version: str) -> dict:
        row = repository.sop_version(sop_id, version)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SOP version not found")
        return row.definition

    @app.post("/api/v1/simulation/scenarios/{scenario}")
    async def run_scenario(scenario: str) -> dict:
        if scenario not in SCENARIOS:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown simulation scenario")
        result = orchestrator.run_scenario(scenario)
        await orchestrator.publish(result)
        return result

    @app.post("/api/v1/simulation/reset")
    async def reset(request: ResetRequest) -> dict:
        repository.reset_station(resolved.station_id, request.actor_id)
        result = orchestrator.station_snapshot(resolved.station_id)
        await orchestrator.publish(result)
        return result

    @app.websocket("/ws/v1/stations/{station_id}")
    async def station_socket(websocket: WebSocket, station_id: str) -> None:
        try:
            initial = orchestrator.station_snapshot(station_id)
        except LookupError:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        queue = orchestrator.subscribe()
        try:
            await websocket.send_json(initial)
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=5)
                except TimeoutError:
                    item = orchestrator.station_snapshot(station_id)
                await websocket.send_json(item)
        except WebSocketDisconnect:
            pass
        finally:
            orchestrator.unsubscribe(queue)

    return app
