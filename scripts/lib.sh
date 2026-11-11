#!/usr/bin/env bash
# Gemeinsame Funktionen für die Deploy-Skripte. Wird mit `source` eingebunden.
# Steuerung über Umgebungsvariablen:
#   DEPLOY_ENV   dev|test|prod   (wählt docker-compose.<env>.yml, Standard: dev)
#   PROXY_PORT   Host-Port des Proxys (Standard 8080)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEPLOY_ENV="${DEPLOY_ENV:-dev}"
PROXY_PORT="${PROXY_PORT:-8080}"
STATE_DIR="$ROOT/.deploy"
STATE_FILE="$STATE_DIR/state.env"
ROUTING_FILE="$ROOT/nginx/conf.d/00-routing.conf"

log()  { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[FEHLER]\033[0m %s\n' "$*" >&2; exit 1; }

# ---- Zustand (aktive Farbe, Image-Tags) --------------------------------------
init_state() {
  mkdir -p "$STATE_DIR"
  if [[ ! -f "$STATE_FILE" ]]; then
    cat >"$STATE_FILE" <<STATE
ACTIVE=blue
PREVIOUS=
BLUE_TAG=local
GREEN_TAG=local
CANARY_TAG=local
CANARY_PERCENT=0
STATE
  fi
}
load_state() {
  init_state
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  export ACTIVE PREVIOUS BLUE_TAG GREEN_TAG CANARY_TAG CANARY_PERCENT
}
save_state() {
  cat >"$STATE_FILE" <<STATE
ACTIVE=${ACTIVE}
PREVIOUS=${PREVIOUS:-}
BLUE_TAG=${BLUE_TAG}
GREEN_TAG=${GREEN_TAG}
CANARY_TAG=${CANARY_TAG}
CANARY_PERCENT=${CANARY_PERCENT:-0}
STATE
}
other_color() { [[ "$1" == "blue" ]] && echo green || echo blue; }
tag_var()     { echo "${1^^}_TAG"; }   # blue -> BLUE_TAG

# ---- Docker Compose -----------------------------------------------------------
compose() {
  local files=(-f docker-compose.yml)
  [[ -f "docker-compose.${DEPLOY_ENV}.yml" ]] && files+=(-f "docker-compose.${DEPLOY_ENV}.yml")
  docker compose "${files[@]}" --profile green --profile canary "$@"
}

# Wartet, bis ALLE Container eines Services "healthy" sind.
wait_healthy() {
  local service="$1" timeout="${2:-90}" waited=0 ids status all
  while (( waited < timeout )); do
    ids="$(compose ps -q "$service")"
    all=1
    if [[ -z "$ids" ]]; then all=0; fi
    for id in $ids; do
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id")"
      [[ "$status" == "healthy" ]] || all=0
    done
    (( all == 1 )) && { log "$service ist healthy"; return 0; }
    sleep 3; waited=$((waited + 3))
  done
  return 1
}

# ---- nginx-Routing (Blue-Green / Canary) -----------------------------------
# write_routing <stable-farbe> [canary-prozent]
write_routing() {
  local stable="$1" pct="${2:-0}"
  if (( pct > 0 )); then
    cat >"$ROUTING_FILE" <<CONF
# Automatisch erzeugt von scripts/lib.sh – nicht von Hand editieren.
# Stabil: app_${stable}, Canary: ${pct} % der Clients (sticky per IP+User-Agent).
split_clients "\${remote_addr}\${http_user_agent}" \$minikos_pool {
    ${pct}% "app_canary";
    *       "app_${stable}";
}
CONF
  else
    cat >"$ROUTING_FILE" <<CONF
# Automatisch erzeugt von scripts/lib.sh – nicht von Hand editieren.
# 100 % auf app_${stable}.
split_clients "\${remote_addr}\${http_user_agent}" \$minikos_pool {
    * "app_${stable}";
}
CONF
  fi
  compose exec -T proxy nginx -t >/dev/null 2>&1 || die "nginx-Konfiguration ungültig"
  compose exec -T proxy nginx -s reload >/dev/null
  log "Routing: stabil=app_${stable}, canary=${pct}%"
}

# Prüft direkt im Docker-Netz (am Proxy vorbei), ob ein Service korrekt antwortet.
probe_service() {
  local service="$1" expect_tag="${2:-}" out
  out="$(compose exec -T proxy wget -qO- "http://${service}:8000/api/version" 2>/dev/null)" || return 1
  [[ -z "$expect_tag" ]] || [[ "$out" == *"$expect_tag"* ]] || { warn "Version passt nicht: $out"; return 1; }
  echo "$out"
}

# Welche Instanz antwortet über den Proxy?
served_by() {
  curl -fsS -o /dev/null -D - "http://localhost:${PROXY_PORT}/health" 2>/dev/null | tr -d '\r' | awk -F': ' 'tolower($1)=="x-served-by"{print $2}'
}
