#!/usr/bin/env bash
# Löst gezielt Störungen aus, um die Alarmkette (Prometheus → Alertmanager → Webhook) zu üben.
# Aufruf: scripts/trigger_alerts.sh errors|slow|down|load [base-url]
# (nur dev/test; /api/sim/* ist in prod abgeschaltet). Bei API_KEY: Umgebungsvariable API_KEY setzen.
source "$(dirname "$0")/lib.sh"
MODE="${1:?Aufruf: $0 errors|slow|down|load [base-url]}"
BASE="${2:-http://localhost:${PROXY_PORT}}"
HDR=(); [[ -n "${API_KEY:-}" ]] && HDR=(-H "X-API-Key: ${API_KEY}")
case "$MODE" in
  errors)
    log "Erzeuge ~5 Minuten lang HTTP-500 → Alert HighErrorRate (nach 2 Min. Pending)"
    for _ in $(seq 1 300); do curl -s -o /dev/null "${HDR[@]}" "$BASE/api/sim/error"; curl -s -o /dev/null "$BASE/health"; sleep 1; done ;;
  slow)
    log "Erzeuge langsame Antworten (3 s) → Alert HighLatency (nach 5 Min.)"
    for _ in $(seq 1 120); do curl -s -o /dev/null "${HDR[@]}" "$BASE/api/sim/slow?sekunden=3" & sleep 2; done; wait ;;
  down)
    load_state
    log "Stoppe app_${ACTIVE} → Alert AppDown/AppAbsent. Wiederherstellen: docker compose start app_${ACTIVE}"
    compose stop "app_${ACTIVE}" ;;
  load)
    log "Normale Last für schöne Grafana-Kurven (60 s)"
    for _ in $(seq 1 60); do curl -s -o /dev/null "$BASE/api/patients"; curl -s -o /dev/null "$BASE/api/stats"; sleep 1; done ;;
  *) die "Unbekannter Modus: $MODE" ;;
esac
log "Fertig. Prüfen: Prometheus ${PROMETHEUS_PORT:-9090}/alerts · Alertmanager ${ALERTMANAGER_PORT:-9093} · docker compose logs alert-webhook"
