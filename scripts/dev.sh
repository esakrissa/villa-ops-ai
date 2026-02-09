#!/usr/bin/env bash
# dev.sh — All-in-one development script for VillaOps AI
#
# Manages code sync, Docker Compose (on remote EC2), and SSH port tunnels.
# Requires: Tailscale connected, remote-workspace SSH host configured.
#
# Usage:
#   ./scripts/dev.sh sync              # One-time rsync to remote
#   ./scripts/dev.sh sync --watch      # Continuous file watching sync
#   ./scripts/dev.sh up                # Sync + docker compose up --build -d
#   ./scripts/dev.sh down              # docker compose down on remote
#   ./scripts/dev.sh restart           # down + up
#   ./scripts/dev.sh logs [service]    # Tail docker compose logs
#   ./scripts/dev.sh ps                # Show container status
#   ./scripts/dev.sh tunnel            # Open SSH tunnels (8000, 5432, 6379)
#   ./scripts/dev.sh tunnel stop       # Kill SSH tunnels
#   ./scripts/dev.sh shell [service]   # Exec into a container (default: backend)
#   ./scripts/dev.sh status            # Show everything: containers, tunnels, sync
#   ./scripts/dev.sh help              # Show this help

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────

REMOTE_HOST="remote-workspace"
REMOTE_DIR="/home/remote/workspace/villa-ops-ai"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TUNNEL_PID_FILE="/tmp/villa-ops-tunnel.pid"

# Ports to tunnel: local:remote
TUNNEL_PORTS=(
    "8000:localhost:8000"   # FastAPI backend
    "5432:localhost:5432"   # PostgreSQL
    "6379:localhost:6379"   # Redis
)

# rsync excludes
EXCLUDES=(
    ".git/"
    ".venv/"
    "venv/"
    "__pycache__/"
    "*.pyc"
    "node_modules/"
    ".next/"
    ".env"
    ".env.local"
    ".env.*.local"
    "PLAN.md"
    ".DS_Store"
    ".idea/"
    ".vscode/"
    "*.egg-info/"
    "dist/"
    "build/"
    ".pytest_cache/"
    "htmlcov/"
    ".coverage"
    ".terraform/"
    "*.tfstate"
    "*.tfstate.backup"
    "postgres_data/"
    "redis_data/"
    ".conductor/"
)

# ─── Colors ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}ℹ${NC}  $*"; }
log_success() { echo -e "${GREEN}✅${NC} $*"; }
log_warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
log_error()   { echo -e "${RED}❌${NC} $*"; }
log_step()    { echo -e "${CYAN}▶${NC}  $*"; }

# ─── Helpers ─────────────────────────────────────────────────────────────────

check_ssh() {
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${REMOTE_HOST}" "true" 2>/dev/null; then
        log_error "Cannot connect to ${REMOTE_HOST}"
        log_info  "Make sure Tailscale is running: tailscale-ctl start"
        log_info  "Make sure EC2 is running: remote-workspace start"
        exit 1
    fi
}

build_exclude_args() {
    local args=()
    for pattern in "${EXCLUDES[@]}"; do
        args+=(--exclude "$pattern")
    done
    echo "${args[@]}"
}

remote_exec() {
    ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && $*"
}

# ─── Commands ────────────────────────────────────────────────────────────────

cmd_sync() {
    local watch_mode=false
    if [[ "${1:-}" == "--watch" || "${1:-}" == "-w" ]]; then
        watch_mode=true
    fi

    check_ssh

    local exclude_args
    read -ra exclude_args <<< "$(build_exclude_args)"

    if [[ "$watch_mode" == true ]]; then
        if ! command -v fswatch &>/dev/null; then
            log_error "fswatch not found. Install with: brew install fswatch"
            exit 1
        fi

        log_info "Watching for changes in ${PROJECT_ROOT}..."
        log_info "Press Ctrl+C to stop"
        echo ""

        # Initial sync
        log_step "Initial sync..."
        rsync -avz --delete "${exclude_args[@]}" "${PROJECT_ROOT}/" "${REMOTE_HOST}:${REMOTE_DIR}/"
        log_success "Sync complete"
        echo ""

        # Watch and sync on changes
        fswatch -o \
            --exclude ".git/" \
            --exclude "__pycache__/" \
            --exclude "node_modules/" \
            --exclude ".next/" \
            --exclude ".venv/" \
            "${PROJECT_ROOT}" | while read -r _; do
            log_step "Changes detected, syncing..."
            rsync -avz --delete "${exclude_args[@]}" "${PROJECT_ROOT}/" "${REMOTE_HOST}:${REMOTE_DIR}/" 2>&1 | grep -E "^(sending|sent|deleting)" || true
            log_success "Sync complete ($(date '+%H:%M:%S'))"
        done
    else
        log_step "Syncing to ${REMOTE_HOST}:${REMOTE_DIR}"
        rsync -avz --delete "${exclude_args[@]}" "${PROJECT_ROOT}/" "${REMOTE_HOST}:${REMOTE_DIR}/"
        log_success "Sync complete"
    fi
}

cmd_up() {
    check_ssh

    log_step "Syncing code to remote..."
    cmd_sync

    echo ""
    log_step "Building and starting containers on remote..."
    remote_exec "docker compose up --build -d" 2>&1

    echo ""
    log_step "Waiting for services to be healthy..."
    sleep 3
    remote_exec "docker compose ps"

    echo ""
    log_success "Services are up on remote!"
    log_info "Access via SSH tunnel: ./scripts/dev.sh tunnel"
    log_info "Or via remote: ssh ${REMOTE_HOST} 'curl http://localhost:8000/health'"
}

cmd_down() {
    check_ssh

    log_step "Stopping containers on remote..."
    remote_exec "docker compose down" 2>&1
    log_success "Containers stopped"
}

cmd_restart() {
    cmd_down
    echo ""
    cmd_up
}

cmd_logs() {
    local service="${1:-}"
    check_ssh

    if [[ -n "$service" ]]; then
        remote_exec "docker compose logs -f --tail 100 ${service}"
    else
        remote_exec "docker compose logs -f --tail 100"
    fi
}

cmd_ps() {
    check_ssh
    remote_exec "docker compose ps"
}

cmd_tunnel() {
    local action="${1:-start}"

    case "$action" in
        stop|kill|down)
            cmd_tunnel_stop
            ;;
        *)
            cmd_tunnel_start
            ;;
    esac
}

cmd_tunnel_start() {
    # Check if tunnel already running
    if [[ -f "$TUNNEL_PID_FILE" ]] && kill -0 "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null; then
        log_warn "Tunnel already running (PID $(cat "$TUNNEL_PID_FILE"))"
        log_info "Stop with: ./scripts/dev.sh tunnel stop"
        return 0
    fi

    check_ssh

    # Build SSH tunnel arguments
    local tunnel_args=()
    for port_spec in "${TUNNEL_PORTS[@]}"; do
        tunnel_args+=(-L "$port_spec")
    done

    log_step "Opening SSH tunnels to ${REMOTE_HOST}..."
    ssh -f -N "${tunnel_args[@]}" "${REMOTE_HOST}"

    # Find the PID of the tunnel process
    local pid
    pid=$(pgrep -f "ssh -f -N.*${REMOTE_HOST}" | tail -1)

    if [[ -n "$pid" ]]; then
        echo "$pid" > "$TUNNEL_PID_FILE"
        log_success "SSH tunnel running (PID ${pid})"
        echo ""
        log_info "Local ports forwarded to remote:"
        for port_spec in "${TUNNEL_PORTS[@]}"; do
            local local_port="${port_spec%%:*}"
            case "$local_port" in
                8000) log_info "  http://localhost:${local_port}  →  FastAPI backend" ;;
                5432) log_info "  localhost:${local_port}          →  PostgreSQL" ;;
                6379) log_info "  localhost:${local_port}          →  Redis" ;;
                *)    log_info "  localhost:${local_port}" ;;
            esac
        done
        echo ""
        log_info "Stop with: ./scripts/dev.sh tunnel stop"
    else
        log_error "Failed to find tunnel process"
        exit 1
    fi
}

cmd_tunnel_stop() {
    if [[ -f "$TUNNEL_PID_FILE" ]]; then
        local pid
        pid=$(cat "$TUNNEL_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            log_success "Tunnel stopped (PID ${pid})"
        else
            log_warn "Tunnel process (PID ${pid}) was not running"
        fi
        rm -f "$TUNNEL_PID_FILE"
    else
        # Try to find and kill any matching tunnel
        local pid
        pid=$(pgrep -f "ssh -f -N.*${REMOTE_HOST}" 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            kill "$pid"
            log_success "Tunnel stopped (PID ${pid})"
        else
            log_info "No tunnel running"
        fi
    fi
}

cmd_shell() {
    local service="${1:-backend}"
    check_ssh

    log_info "Exec into ${service}..."
    ssh -t "${REMOTE_HOST}" "cd ${REMOTE_DIR} && docker compose exec ${service} bash || docker compose exec ${service} sh"
}

cmd_status() {
    echo -e "${CYAN}═══ VillaOps AI — Dev Status ═══${NC}"
    echo ""

    # SSH connection
    log_step "Remote connection..."
    if ssh -o ConnectTimeout=3 -o BatchMode=yes "${REMOTE_HOST}" "true" 2>/dev/null; then
        log_success "SSH to ${REMOTE_HOST}: connected"
    else
        log_error "SSH to ${REMOTE_HOST}: unreachable"
        return 0
    fi

    # Docker containers
    echo ""
    log_step "Docker containers:"
    remote_exec "docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'" 2>/dev/null || log_warn "No containers found"

    # SSH tunnel
    echo ""
    log_step "SSH tunnel:"
    if [[ -f "$TUNNEL_PID_FILE" ]] && kill -0 "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null; then
        log_success "Tunnel running (PID $(cat "$TUNNEL_PID_FILE"))"
        for port_spec in "${TUNNEL_PORTS[@]}"; do
            local local_port="${port_spec%%:*}"
            log_info "  localhost:${local_port} → remote"
        done
    else
        log_warn "No tunnel running"
    fi

    # Health check
    echo ""
    log_step "Health check:"
    local health
    health=$(remote_exec "curl -s --connect-timeout 3 http://localhost:8000/health" 2>/dev/null || echo "UNREACHABLE")
    if [[ "$health" == *"healthy"* ]]; then
        log_success "FastAPI: ${health}"
    else
        log_warn "FastAPI: ${health}"
    fi
}

cmd_help() {
    cat <<'EOF'

  VillaOps AI — Development Helper
  ─────────────────────────────────

  Usage: ./scripts/dev.sh <command> [options]

  Commands:
    sync              One-time rsync code to remote EC2
    sync --watch      Continuous file-watching sync (requires fswatch)
    up                Sync + build + start all containers
    down              Stop and remove containers
    restart           Down + Up
    logs [service]    Tail container logs (all or specific service)
    ps                Show container status
    tunnel            Open SSH tunnels (localhost:8000/5432/6379)
    tunnel stop       Close SSH tunnels
    shell [service]   Exec into a container (default: backend)
    status            Show connection, containers, and tunnel status
    help              Show this help

  Examples:
    ./scripts/dev.sh up                # Start everything
    ./scripts/dev.sh tunnel            # Access via localhost:8000
    ./scripts/dev.sh logs backend      # Watch backend logs
    ./scripts/dev.sh sync --watch      # Auto-sync on file changes
    ./scripts/dev.sh shell backend     # Shell into backend container
    ./scripts/dev.sh down              # Stop everything

  Workflow:
    1. ./scripts/dev.sh up             # Sync code + start containers
    2. ./scripts/dev.sh tunnel         # Forward ports to localhost
    3. Open http://localhost:8000/docs  # Access API docs
    4. Edit code locally, then:
       ./scripts/dev.sh sync           # Push changes (hot reload picks them up)
       OR
       ./scripts/dev.sh sync --watch   # Auto-sync on every save

EOF
}

# ─── Main ────────────────────────────────────────────────────────────────────

command="${1:-help}"
shift || true

case "$command" in
    sync)       cmd_sync "$@" ;;
    up)         cmd_up "$@" ;;
    down)       cmd_down "$@" ;;
    restart)    cmd_restart "$@" ;;
    logs)       cmd_logs "$@" ;;
    ps)         cmd_ps "$@" ;;
    tunnel)     cmd_tunnel "$@" ;;
    shell|exec) cmd_shell "$@" ;;
    status)     cmd_status "$@" ;;
    help|--help|-h) cmd_help ;;
    *)
        log_error "Unknown command: ${command}"
        cmd_help
        exit 1
        ;;
esac
