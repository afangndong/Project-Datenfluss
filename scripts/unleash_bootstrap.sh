#!/usr/bin/env bash
# Legt die Feature Flags der App in Unleash an und schaltet sie in "development" ein.
# Voraussetzung: make up-flags  (Unleash läuft auf :4242). Aktiviert danach die Flag-Anbindung der App:
#   env/dev.env → UNLEASH_URL und UNLEASH_TOKEN einkommentieren, dann `docker compose restart app_blue`.
set -euo pipefail
URL="${UNLEASH_ADMIN_URL:-http://localhost:${UNLEASH_PORT:-4242}}"
TOKEN="${UNLEASH_ADMIN_TOKEN:-*:*.unleash-insecure-admin-token}"   # Demo-Token aus docker-compose.yml
for i in $(seq 1 30); do curl -fsS "$URL/health" >/dev/null 2>&1 && break; echo "warte auf Unleash … ($i)"; sleep 3; done
for flag in neues_dashboard wartungshinweis; do
  curl -sS -o /dev/null -w "create $flag → HTTP %{http_code}\n" -X POST "$URL/api/admin/projects/default/features" \
    -H "Authorization: $TOKEN" -H 'Content-Type: application/json' -d "{\"name\":\"$flag\",\"type\":\"release\"}"
done
curl -sS -o /dev/null -w "enable neues_dashboard → HTTP %{http_code}\n" -X POST \
  "$URL/api/admin/projects/default/features/neues_dashboard/environments/development/on" -H "Authorization: $TOKEN"
echo "Fertig. Flags im UI schalten: $URL  (Login admin / unleash4all – nur Demo!)"
