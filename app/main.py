"""Mini-KOS – FastAPI-Anwendung."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .logging_conf import setup_logging
from .metrics import metrics_middleware
from .routers import appointments, patients, stays, system

setup_logging()
log = logging.getLogger("minikos")
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # Demo: kein Alembic nötig
    log.info("Mini-KOS gestartet (env=%s, version=%s)", settings.app_env, settings.app_version)
    yield


app = FastAPI(
    title="Mini-KOS",
    description="Demo eines Klinik-Informationssystems – Patienten, Aufenthalte, Termine.",
    version=settings.app_version,
    lifespan=lifespan,
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Served-By"] = settings.instance_name
    if request.url.path not in ("/health", "/metrics", "/ready"):
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,  # bewusst ohne Query-String (kann Suchbegriffe/Namen enthalten)
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "request_id": request_id,
            },
        )
    return response


app.middleware("http")(metrics_middleware)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unbehandelter Fehler", extra={"path": request.url.path, "method": request.method})
    return JSONResponse({"detail": "Interner Fehler"}, status_code=500)


for r in (system.router, patients.router, stays.router, appointments.router):
    app.include_router(r)

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
