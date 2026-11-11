#!/usr/bin/env bash
# Schaltet auf die zuvor aktive Farbe zurück (Blue-Green-Rollback, Sekunden statt Minuten).
source "$(dirname "$0")/lib.sh"
load_state
[[ -n "${PREVIOUS:-}" ]] || die "Keine vorherige Version bekannt (.deploy/state.env)"
log "Rollback: $ACTIVE → $PREVIOUS"
compose up -d --no-deps "app_${PREVIOUS}"
wait_healthy "app_${PREVIOUS}" 90 || die "app_${PREVIOUS} nicht gesund – Rollback abgebrochen"
write_routing "$PREVIOUS" 0
FAILED="$ACTIVE"; ACTIVE="$PREVIOUS"; PREVIOUS="$FAILED"; export CANARY_PERCENT=0
save_state
log "Aktiv ist jetzt wieder: $ACTIVE (fehlerhafte Version $FAILED läuft zur Analyse weiter)"
