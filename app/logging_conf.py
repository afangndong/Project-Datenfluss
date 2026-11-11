"""Strukturiertes JSON-Logging für Filebeat/Logstash/Elasticsearch.

DSGVO/Datenschutz: Es werden NIE Klartext-Patientendaten geloggt – nur technische IDs.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from .config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "@timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": settings.app_name,
            "env": settings.app_env,
            "instance": settings.instance_name,
            "version": settings.app_version,
        }
        for key in ("method", "path", "status", "duration_ms", "request_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    logging.getLogger("uvicorn.access").disabled = True  # eigenes Access-Log in der Middleware
