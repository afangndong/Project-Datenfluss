"""Minimaler Alertmanager-Webhook-Empfänger (nur Standardbibliothek).

- schreibt jede Meldung als JSON-Zeile auf stdout (→ docker logs → Filebeat → ELK)
- leitet optional an Slack weiter, wenn SLACK_WEBHOOK_URL gesetzt ist
- bewusst OHNE Patientendaten: Alerts enthalten nur technische Labels
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

SLACK = os.getenv("SLACK_WEBHOOK_URL", "")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        prio = parse_qs(urlparse(self.path).query).get("prio", ["info"])[0]
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        for alert in body.get("alerts", []):
            line = {
                "event": "alert",
                "prio": prio,
                "status": alert.get("status"),
                "alertname": alert.get("labels", {}).get("alertname"),
                "summary": alert.get("annotations", {}).get("summary"),
                "runbook": alert.get("annotations", {}).get("runbook"),
            }
            print(json.dumps(line, ensure_ascii=False), flush=True)
            if SLACK:
                icon = "🔥" if prio == "critical" else "⚠️"
                text = f"{icon} [{alert.get('status')}] {line['alertname']}: {line['summary']}"
                req = urllib.request.Request(  # noqa: S310
                    SLACK, json.dumps({"text": text}).encode(), {"Content-Type": "application/json"}
                )
                try:
                    urllib.request.urlopen(req, timeout=5)  # noqa: S310
                except Exception as exc:
                    print(json.dumps({"event": "slack_error", "error": str(exc)}), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print("alert-webhook lauscht auf :9095", flush=True)
    HTTPServer(("0.0.0.0", 9095), Handler).serve_forever()  # noqa: S104
