#!/usr/bin/env bash
# local-dev.sh — Run VillaOps AI locally with Docker Compose on this machine.
#
# Starts Docker Desktop if needed, brings the stack up, waits until every
# service answers, and prints where to open the app.
#
# Usage:
#   ./scripts/local-dev.sh --start     # start everything (builds images on first run)
#   ./scripts/local-dev.sh --restart   # recreate containers (re-reads .env)
#   ./scripts/local-dev.sh --stop      # stop all containers (data is kept)
#   ./scripts/local-dev.sh --status    # show whether each service is live

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WAIT_SECONDS=${WAIT_SECONDS:-180}

# name | url | required (1 = the app is not usable without it)
SERVICES=(
  "Frontend|http://localhost:3000|1"
  "Backend API|http://localhost:8000/health|1"
  "VillaOps MCP|http://localhost:8001/health|1"
  "Booking.com MCP|http://localhost:8002/health|0"
  "Airbnb MCP|http://localhost:8003/health|0"
  "Tripadvisor MCP|http://localhost:8004/health|0"
)

if [[ -t 1 ]]; then
  GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
  GREEN=""; RED=""; YELLOW=""; DIM=""; BOLD=""; RESET=""
fi

info() { echo "${DIM}›${RESET} $*"; }
ok()   { echo "${GREEN}✓${RESET} $*"; }
warn() { echo "${YELLOW}!${RESET} $*"; }
fail() { echo "${RED}✗${RESET} $*" >&2; }

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

ensure_docker() {
  if docker info >/dev/null 2>&1; then
    return
  fi
  if [[ "$(uname)" == "Darwin" ]] && [[ -d /Applications/Docker.app ]]; then
    info "Docker isn't running — opening Docker Desktop…"
    open -a Docker
    for _ in $(seq 1 60); do
      if docker info >/dev/null 2>&1; then
        ok "Docker is running"
        return
      fi
      sleep 2
    done
  fi
  fail "Docker is not running. Start Docker Desktop and try again."
  exit 1
}

ensure_env() {
  if [[ ! -f .env ]]; then
    fail "No .env found in $ROOT. Copy .env.example to .env and fill in the keys."
    exit 1
  fi
}

is_live() {
  local code
  code=$(curl -s -o /dev/null -m 3 -w "%{http_code}" "$1" || true)
  [[ "$code" =~ ^(2|3)[0-9][0-9]$ ]]
}

wait_for_services() {
  local deadline=$((SECONDS + WAIT_SECONDS))
  info "Waiting for services (up to ${WAIT_SECONDS}s)…"
  for entry in "${SERVICES[@]}"; do
    IFS='|' read -r name url _ <<<"$entry"
    until is_live "$url"; do
      if ((SECONDS >= deadline)); then
        break 2
      fi
      sleep 2
    done
  done
}

print_status() {
  local down_required=0
  echo
  echo "${BOLD}VillaOps AI — local services${RESET}"
  for entry in "${SERVICES[@]}"; do
    IFS='|' read -r name url required <<<"$entry"
    if is_live "$url"; then
      printf "  ${GREEN}●${RESET} %-16s ${GREEN}live${RESET}  ${DIM}%s${RESET}\n" "$name" "$url"
    elif [[ "$required" == "1" ]]; then
      printf "  ${RED}●${RESET} %-16s ${RED}down${RESET}  ${DIM}%s${RESET}\n" "$name" "$url"
      down_required=1
    else
      printf "  ${YELLOW}●${RESET} %-16s ${YELLOW}down${RESET}  ${DIM}%s (optional)${RESET}\n" "$name" "$url"
    fi
  done
  echo
  if ((down_required)); then
    fail "Some required services are not live. Check logs with: docker compose logs -f backend frontend"
    return 1
  fi
  ok "${BOLD}VillaOps AI is live → http://localhost:3000${RESET}"
  echo "  ${DIM}API docs: http://localhost:8000/docs · Logs: docker compose logs -f backend${RESET}"
}

start() {
  ensure_docker
  ensure_env
  info "Starting containers (first run builds images and can take ~10 min)…"
  docker compose up -d --build
  wait_for_services
  print_status
}

restart() {
  ensure_docker
  ensure_env
  # --force-recreate re-reads .env (plain `docker compose restart` does not)
  info "Recreating containers…"
  docker compose up -d --build --force-recreate
  wait_for_services
  print_status
}

stop() {
  ensure_docker
  info "Stopping containers (database and Redis data are kept)…"
  docker compose stop
  ok "VillaOps AI stopped"
}

case "${1:-}" in
  --start) start ;;
  --restart) restart ;;
  --stop) stop ;;
  --status) ensure_docker; print_status ;;
  -h | --help | "") usage ;;
  *)
    fail "Unknown option: $1"
    usage
    exit 1
    ;;
esac
