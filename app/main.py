"""FastAPI application: REST control plane, SSE metrics stream, SPA hosting."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .auth import clear_session, issue_session, require_auth, verify_password
from .config import settings
from .metrics import host_metrics
from .services.manager import ServiceManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

manager = ServiceManager(
    services_dir=settings.services_dir,
    venvs_dir=settings.venvs_dir,
    logs_dir=settings.logs_dir,
    state_file=settings.state_file,
    pip_extra_index_url=settings.pip_extra_index_url,
    stop_timeout=settings.stop_timeout,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(manager.startup)
    poll_task = asyncio.create_task(_poll_loop())
    try:
        yield
    finally:
        poll_task.cancel()
        await asyncio.to_thread(manager.shutdown)


async def _poll_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(manager.poll)
        except Exception:  # noqa: BLE001 - never let the supervisor die
            logging.exception("poll loop error")
        await asyncio.sleep(settings.metrics_interval)


app = FastAPI(title="PiServiceUi", lifespan=lifespan)


# --------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
async def login(body: LoginRequest, response: Response):
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    issue_session(response)
    return {"ok": True}


@app.post("/api/logout")
async def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@app.get("/api/auth/check")
async def auth_check(_: bool = Depends(require_auth)):
    return {"ok": True}


# --------------------------------------------------------------------- #
# Services
# --------------------------------------------------------------------- #
@app.get("/api/services")
async def list_services(_: bool = Depends(require_auth)):
    return {"services": manager.list()}


@app.post("/api/services/rescan")
async def rescan(_: bool = Depends(require_auth)):
    await asyncio.to_thread(manager.discover)
    return {"services": manager.list()}


def _run(action, name: str):
    try:
        action(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such service: {name}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/services/{name}/start")
async def start_service(name: str, _: bool = Depends(require_auth)):
    await asyncio.to_thread(_run, manager.start, name)
    return {"ok": True}


@app.post("/api/services/{name}/stop")
async def stop_service(name: str, _: bool = Depends(require_auth)):
    await asyncio.to_thread(_run, manager.stop, name)
    return {"ok": True}


@app.post("/api/services/{name}/restart")
async def restart_service(name: str, _: bool = Depends(require_auth)):
    await asyncio.to_thread(_run, manager.restart, name)
    return {"ok": True}


@app.get("/api/services/{name}/logs")
async def service_logs(name: str, lines: int = 200, _: bool = Depends(require_auth)):
    try:
        return {"lines": manager.get_logs(name, max(1, min(lines, 2000)))}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such service: {name}")


# --------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------- #
@app.get("/api/metrics/host")
async def metrics_host(_: bool = Depends(require_auth)):
    return host_metrics()


@app.get("/api/stream")
async def stream(request: Request, _: bool = Depends(require_auth)):
    async def gen():
        while True:
            if await request.is_disconnected():
                break
            payload = {"host": host_metrics(), "services": manager.list()}
            yield {"event": "snapshot", "data": json.dumps(payload)}
            await asyncio.sleep(settings.metrics_interval)

    return EventSourceResponse(gen())


# --------------------------------------------------------------------- #
# Static SPA (built React bundle). Registered last so /api/* wins.
# --------------------------------------------------------------------- #
WEB_DIST = Path(settings.web_dist_dir).resolve()


@app.get("/{full_path:path}")
async def spa(full_path: str):
    if not WEB_DIST.exists():
        return Response(
            "Frontend not built. Run `npm run build` in web/ (or use the dev server).",
            media_type="text/plain",
            status_code=503,
        )
    if full_path:
        candidate = (WEB_DIST / full_path).resolve()
        # Guard against path traversal: only serve files inside the bundle.
        if candidate.is_file() and WEB_DIST in candidate.parents:
            return FileResponse(candidate)
    return FileResponse(WEB_DIST / "index.html")
