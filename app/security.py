"""Minimaler API-Key-Schutz für Schreibzugriffe (Demo, kein Ersatz für echtes IAM)."""

import secrets

from fastapi import Header, HTTPException

from .config import settings


def require_write_access(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return  # Demo-Modus: offen
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="API-Key fehlt oder ist ungültig")
