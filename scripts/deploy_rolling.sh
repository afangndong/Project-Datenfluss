#!/usr/bin/env bash
# Rolling Update: Replikas einzeln austauschen (erst neu starten + prüfen, dann alt entfernen).
# Vorteil: keine Downtime, wenig Zusatzressourcen. Nachteil: kurz laufen zwei Versionen gleichzeitig.
# Aufruf: scripts/deploy_rolling.sh <image-tag> [replikas=2]
source "$(dirname "$0")/lib.sh"
TAG="${1:?Aufruf: $0 <image-tag> [replikas]}"
REPLICAS="${2:-2}"

load_state
SERVICE="app_${ACTIVE}"
OLD_TAG_VAR="$(tag_var "$ACTIVE")"
OLD_TAG="${!OLD_TAG_VAR}"
log "Rolling Update $SERVICE: $OLD_TAG → $TAG (Ziel: $REPLICAS Replikas)"

export "$OLD_TAG_VAR=$TAG"   # neue Container bekommen die neue Version
mapfile -t OLD_IDS < <(compose ps -q "$SERVICE")
CURRENT=${#OLD_IDS[@]}
(( CURRENT > 0 )) || { log "Keine laufende Instanz – starte frisch"; compose up -d --no-deps --scale "$SERVICE=$REPLICAS" "$SERVICE"; wait_healthy "$SERVICE" 120; printf -v "$OLD_TAG_VAR" '%s' "$TAG"; save_state; exit 0; }

for old in "${OLD_IDS[@]}"; do
  CURRENT=$((CURRENT + 1))
  mapfile -t BEFORE < <(compose ps -q "$SERVICE")
  compose up -d --no-deps --no-recreate --scale "$SERVICE=$CURRENT" "$SERVICE"
  mapfile -t AFTER < <(compose ps -q "$SERVICE")
  NEW_ID="$(comm -13 <(printf '%s\n' "${BEFORE[@]}" | sort) <(printf '%s\n' "${AFTER[@]}" | sort) | head -1)"
  [[ -n "$NEW_ID" ]] || die "Neuer Container nicht gefunden"

  log "Warte auf neuen Container ${NEW_ID:0:12} …"
  for _ in $(seq 1 40); do
    st="$(docker inspect -f '{{.State.Health.Status}}' "$NEW_ID" 2>/dev/null || echo starting)"
    [[ "$st" == "healthy" ]] && break
    [[ "$st" == "unhealthy" ]] && break
    sleep 3
  done
  if [[ "$st" != "healthy" ]]; then
    warn "Neuer Container wurde nicht gesund ($st) – Abbruch, alte Replikas bleiben aktiv"
    docker logs --tail 30 "$NEW_ID" || true
    docker rm -f "$NEW_ID" >/dev/null
    printf -v "$OLD_TAG_VAR" '%s' "$OLD_TAG"; export "$OLD_TAG_VAR=$OLD_TAG"
    exit 1
  fi
  log "Entferne alten Container ${old:0:12}"
  docker stop --time 20 "$old" >/dev/null && docker rm "$old" >/dev/null
  CURRENT=$((CURRENT - 1))
  sleep 2   # nginx löst per DNS (valid=5s) neu auf
done

# Auf Ziel-Replikazahl bringen
compose up -d --no-deps --no-recreate --scale "$SERVICE=$REPLICAS" "$SERVICE"
wait_healthy "$SERVICE" 120 || die "Nicht alle Replikas gesund"
printf -v "$OLD_TAG_VAR" '%s' "$TAG"
save_state
log "Rolling Update abgeschlossen: $REPLICAS Replikas auf Tag $TAG"
