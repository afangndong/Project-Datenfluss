#!/usr/bin/env bash
# Blue-Green: neue Version parallel starten, prüfen, dann Traffic atomar umschalten.
# Vorteil: keine Downtime, Rollback in Sekunden (scripts/rollback.sh). Nachteil: doppelte Ressourcen.
# Aufruf: scripts/deploy_bluegreen.sh <image-tag> [--stop-old]
source "$(dirname "$0")/lib.sh"
TAG="${1:?Aufruf: $0 <image-tag> [--stop-old]}"
STOP_OLD="${2:-}"

load_state
TARGET="$(other_color "$ACTIVE")"
log "Blue-Green: aktiv=$ACTIVE → neu=$TARGET (Tag $TAG)"

export "$(tag_var "$TARGET")=$TAG"
printf -v "$(tag_var "$TARGET")" '%s' "$TAG"

compose up -d --no-deps --pull missing "app_${TARGET}"
if ! wait_healthy "app_${TARGET}" 120 || ! probe_service "app_${TARGET}" >/dev/null; then
  warn "app_${TARGET} wurde nicht gesund – Abbruch, Produktion bleibt auf $ACTIVE"
  compose logs --tail 30 "app_${TARGET}" || true
  compose stop "app_${TARGET}" || true
  exit 1
fi

write_routing "$TARGET" 0
sleep 1
SERVED="$(served_by || true)"
[[ "$SERVED" == "$TARGET" ]] || { warn "Proxy liefert '$SERVED' statt '$TARGET' – schalte zurück"; write_routing "$ACTIVE" 0; exit 1; }

PREVIOUS="$ACTIVE"; ACTIVE="$TARGET"; export CANARY_PERCENT=0
save_state
log "Umschaltung erfolgreich. Aktiv: $ACTIVE (Tag $TAG). Vorherige Version bleibt für Rollback laufen."

if [[ "$STOP_OLD" == "--stop-old" ]]; then
  compose stop "app_${PREVIOUS}"; log "app_${PREVIOUS} gestoppt (Rollback nur noch per Neustart)"
fi
