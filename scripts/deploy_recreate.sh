#!/usr/bin/env bash
# Recreate: alte Version stoppen, neue starten. EINFACH, aber mit kurzer Downtime.
# Sinnvoll bei Wartungsfenstern oder nicht abwärtskompatiblen DB-Migrationen.
# Aufruf: scripts/deploy_recreate.sh <image-tag>
source "$(dirname "$0")/lib.sh"
TAG="${1:?Aufruf: $0 <image-tag>}"
load_state
SERVICE="app_${ACTIVE}"; VAR="$(tag_var "$ACTIVE")"
export "$VAR=$TAG"
log "Recreate $SERVICE → Tag $TAG (kurze Downtime!)"
compose stop "$SERVICE"
compose up -d --no-deps --force-recreate "$SERVICE"
wait_healthy "$SERVICE" 120 || { compose logs --tail 30 "$SERVICE"; die "Neue Version nicht gesund"; }
printf -v "$VAR" '%s' "$TAG"; save_state
log "Fertig: $SERVICE läuft mit Tag $TAG"
