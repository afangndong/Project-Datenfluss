"""Prometheus-Metriken (RED: Rate, Errors, Duration) + Fachmetriken."""

import time

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import func, select

from .db import SessionLocal
from .models import Appointment, Patient, Stay

REQUESTS = Counter("minikos_http_requests_total", "HTTP-Requests", ["method", "path", "status"])
LATENCY = Histogram(
    "minikos_http_request_duration_seconds",
    "Latenz je Route",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
IN_PROGRESS = Gauge("minikos_http_requests_in_progress", "Laufende Requests")
PATIENTS = Gauge("minikos_patients_total", "Anzahl Patienten")
ACTIVE_STAYS = Gauge("minikos_active_stays", "Aktuelle stationäre Aufenthalte")
OPEN_APPTS = Gauge("minikos_open_appointments", "Offene (geplante) Termine")
DB_UP = Gauge("minikos_db_up", "1 = Datenbank erreichbar")


def refresh_business_gauges() -> None:
    """Wird bei jedem Scrape von /metrics aufgerufen (günstige COUNT-Queries)."""
    try:
        with SessionLocal() as db:
            PATIENTS.set(db.scalar(select(func.count(Patient.id))) or 0)
            ACTIVE_STAYS.set(db.scalar(select(func.count(Stay.id)).where(Stay.entlassung.is_(None))) or 0)
            OPEN_APPTS.set(db.scalar(select(func.count(Appointment.id)).where(Appointment.status == "geplant")) or 0)
        DB_UP.set(1)
    except Exception:
        DB_UP.set(0)


async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    IN_PROGRESS.inc()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        IN_PROGRESS.dec()
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        if path not in ("/metrics",):
            REQUESTS.labels(request.method, path, str(status)).inc()
            LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
