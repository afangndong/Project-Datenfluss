"""Feature Flags: Unleash (optional) mit Fallback auf Umgebungsvariablen FEATURE_<NAME>.

Bekannte Flags:
  neues_dashboard   – zeigt in der GUI zusätzliche Statistik-Karten
  wartungshinweis   – zeigt in der GUI ein Wartungsbanner
"""

import json
import logging
import os
import time
import urllib.request

from .config import settings

log = logging.getLogger("minikos.flags")

KNOWN_FLAGS = {"neues_dashboard": True, "wartungshinweis": False}
_cache: dict = {"ts": 0.0, "data": {}}
_TTL = 15.0


def _fetch_unleash() -> dict[str, bool]:
    req = urllib.request.Request(
        f"{settings.unleash_url.rstrip('/')}/api/client/features",
        headers={"Authorization": settings.unleash_token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        body = json.loads(resp.read())
    # Vereinfachung: Flag gilt als an, wenn enabled=true (Strategien werden nicht ausgewertet).
    return {f["name"]: bool(f.get("enabled")) for f in body.get("features", [])}


def _remote_flags() -> dict[str, bool]:
    now = time.monotonic()
    if now - _cache["ts"] < _TTL:
        return _cache["data"]
    try:
        _cache["data"] = _fetch_unleash()
    except Exception as exc:  # Unleash down darf die App nie lahmlegen
        log.warning("Unleash nicht erreichbar, nutze Fallback: %s", exc)
    _cache["ts"] = now
    return _cache["data"]


def is_enabled(name: str) -> bool:
    if settings.unleash_url and settings.unleash_token:
        remote = _remote_flags()
        if name in remote:
            return remote[name]
    env = os.getenv(f"FEATURE_{name.upper()}")
    if env is not None:
        return env.lower() in ("1", "true", "yes", "on")
    return KNOWN_FLAGS.get(name, False)


def all_flags() -> dict[str, bool]:
    return {name: is_enabled(name) for name in KNOWN_FLAGS}
