#!/usr/bin/env bash
# Canary: neue Version bekommt zunächst nur X % des Traffics. Bei guten Metriken → promoten.
# Aufruf: scripts/deploy_canary.sh <image-tag> [prozent=10]     starten
#         scripts/deploy_canary.sh --promote                     Canary wird neue Hauptversion (Blue-Green)
#         scripts/deploy_canary.sh --abort                       Canary verwerfen
source "$(dirname "$0")/lib.sh"
load_state

case "${1:-}" in
  --abort)
    write_routing "$ACTIVE" 0
    compose stop app_canary || true
    CANARY_PERCENT=0; save_state; log "Canary verworfen"; exit 0 ;;
  --promote)
    [[ "$CANARY_PERCENT" -gt 0 ]] || die "Kein Canary aktiv"
    "$ROOT/scripts/deploy_bluegreen.sh" "$CANARY_TAG"
    compose stop app_canary || true
    exit 0 ;;
  "") die "Aufruf: $0 <image-tag> [prozent] | --promote | --abort" ;;
esac

TAG="$1"; PCT="${2:-10}"
(( PCT >= 1 && PCT <= 100 )) || die "Prozent muss 1–100 sein"
CANARY_TAG="$TAG"; export CANARY_TAG
compose up -d --no-deps app_canary
wait_healthy app_canary 120 || { compose logs --tail 30 app_canary; compose stop app_canary; die "Canary nicht gesund – nicht ausgerollt"; }
write_routing "$ACTIVE" "$PCT"
CANARY_PERCENT="$PCT"; save_state
log "Canary läuft mit $PCT % (Tag $TAG). Beobachten: Grafana → 'Requests/s je Instanz', Fehlerrate, Latenz (Label pool=app_canary)."
log "Weiter: $0 --promote   oder   $0 --abort"
