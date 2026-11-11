#!/usr/bin/env bash
# Rauchtest gegen eine laufende Instanz (Health, Readiness, Version, Lesen, Schreiben+Löschen).
# Aufruf: scripts/smoke_test.sh [base-url]   (Standard http://localhost:8080)   Optional: API_KEY=…
set -euo pipefail
BASE="${1:-http://localhost:8080}"
HDR=(); [[ -n "${API_KEY:-}" ]] && HDR=(-H "X-API-Key: ${API_KEY}")
ok()  { printf '  \033[32m✔\033[0m %s\n' "$1"; }
bad() { printf '  \033[31m✖\033[0m %s\n' "$1"; exit 1; }

echo "Smoke-Test gegen $BASE"
curl -fsS "$BASE/health" >/dev/null && ok "/health" || bad "/health"
curl -fsS "$BASE/ready"  >/dev/null && ok "/ready (DB erreichbar)" || bad "/ready"
VER="$(curl -fsS "$BASE/api/version")" && ok "/api/version → $VER" || bad "/api/version"
curl -fsS "$BASE/api/stats" >/dev/null && ok "/api/stats" || bad "/api/stats"
curl -fsS "$BASE/" | grep -q "Mini-KOS" && ok "GUI wird ausgeliefert" || bad "GUI"
ID="$(curl -fsS "${HDR[@]}" -X POST "$BASE/api/patients" -H 'Content-Type: application/json' \
  -d '{"vorname":"Smoke","nachname":"Test","geburtsdatum":"1990-01-01"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')" \
  && ok "Patient anlegen (id=$ID)" || bad "Patient anlegen"
curl -fsS "${HDR[@]}" -X DELETE "$BASE/api/patients/$ID" -o /dev/null && ok "Patient löschen" || bad "Patient löschen"
curl -fsS "$BASE/metrics" 2>/dev/null | grep -q minikos_http_requests_total && ok "/metrics" || echo "  (i) /metrics ist über den Proxy gesperrt – gewollt"
echo "SMOKE-TEST BESTANDEN"
