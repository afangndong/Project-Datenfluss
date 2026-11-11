"""Betriebs-Endpunkte: Health, Readiness, Version, Flags, Statistik, Metrics, Simulation."""

import asyncio
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import flags
from ..config import settings
from ..db import get_db
from ..metrics import refresh_business_gauges
from ..models import Appointment, Patient, Stay
from ..schemas import Stats
from ..security import require_write_access

router = APIRouter(tags=["System"])


@router.get("/health", summary="Liveness – Prozess lebt")
def health():
    return {"status": "ok"}


@router.get("/ready", summary="Readiness – Datenbank erreichbar")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Datenbank nicht erreichbar") from exc
    return {"status": "ready"}


@router.get("/api/version")
def version():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "git_sha": settings.git_sha,
        "env": settings.app_env,
        "instance": settings.instance_name,
    }


@router.get("/api/flags")
def get_flags():
    return flags.all_flags()


@router.get("/api/links")
def links():
    return {
        "Grafana": settings.grafana_url,
        "Prometheus": settings.prometheus_url,
        "Alertmanager": settings.alertmanager_url,
        "Kibana (ELK)": settings.kibana_url,
        "Unleash (Feature Flags)": settings.unleash_ui_url,
        "API-Doku (Swagger)": "/docs",
    }


@router.get("/api/stats", response_model=Stats)
def stats(db: Session = Depends(get_db)):
    heute = date.today()
    start = datetime.combine(heute, time.min)
    ende = start + timedelta(days=1)
    stationen = db.execute(
        select(Stay.station, func.count(Stay.id)).where(Stay.entlassung.is_(None)).group_by(Stay.station)
    ).all()
    status = db.execute(select(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status)).all()
    return Stats(
        patienten=db.scalar(select(func.count(Patient.id))) or 0,
        aktuelle_aufenthalte=sum(c for _, c in stationen),
        termine_heute=db.scalar(
            select(func.count(Appointment.id)).where(Appointment.termin >= start, Appointment.termin < ende)
        )
        or 0,
        termine_offen=dict(status).get("geplant", 0),
        belegung_je_station=dict(stationen),
        termine_nach_status=dict(status),
    )


@router.get("/metrics", include_in_schema=False)
def metrics():
    refresh_business_gauges()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---- Störungs-Simulation (für Alert-/Support-Übungen; in prod deaktiviert) ----
def _sim_allowed() -> None:
    if settings.app_env == "prod":
        raise HTTPException(404, "Nicht verfügbar")


@router.get("/api/sim/error", dependencies=[Depends(require_write_access)], include_in_schema=False)
def sim_error():
    _sim_allowed()
    raise RuntimeError("Simulierter Fehler (Alert-Test)")


@router.get("/api/sim/slow", dependencies=[Depends(require_write_access)], include_in_schema=False)
async def sim_slow(sekunden: float = 2.0):
    _sim_allowed()
    await asyncio.sleep(min(max(sekunden, 0), 10))
    return {"verzoegert_um": sekunden}
