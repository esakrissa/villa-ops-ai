#!/usr/bin/env bash
# sync.sh — Sync local code to remote EC2 workspace over Tailscale
#
# Usage:
#   ./scripts/sync.sh          # One-time sync
#   ./scripts/sync.sh --watch  # Continuous sync (requires fswatch)

set -euo pipefail

# --- Config ---
REMOTE_HOST="remote-workspace"
REMOTE_PATH="/home/remote/workspace/villa-ops-ai/"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Files/dirs to exclude from sync (already in .gitignore or not needed on remote)
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
    ".claude/"
    "screenshots/"
)

# Build rsync exclude args
EXCLUDE_ARGS=()
for pattern in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS+=(--exclude "$pattern")
done

sync_once() {
    echo "🔄 Syncing to ${REMOTE_HOST}:${REMOTE_PATH}"
    rsync -avz --delete \
        "${EXCLUDE_ARGS[@]}" \
        "${PROJECT_ROOT}/" \
        "${REMOTE_HOST}:${REMOTE_PATH}"
    echo "✅ Sync complete"
}

sync_watch() {
    if ! command -v fswatch &>/dev/null; then
        echo "❌ fswatch not found. Install with: brew install fswatch"
        exit 1
    fi

    echo "👀 Watching for changes in ${PROJECT_ROOT}..."
    echo "   Press Ctrl+C to stop"
    echo ""

    # Initial sync
    sync_once
    echo ""

    # Watch for changes and sync
    fswatch -o \
        --exclude ".git/" \
        --exclude "__pycache__/" \
        --exclude "node_modules/" \
        --exclude ".next/" \
        --exclude ".venv/" \
        "${PROJECT_ROOT}" | while read -r _; do
        sync_once
        echo ""
    done
}

# --- Main ---
case "${1:-}" in
    --watch | -w)
        sync_watch
        ;;
    --help | -h)
        echo "Usage: $0 [--watch|-w] [--help|-h]"
        echo ""
        echo "  (no args)    One-time sync to remote"
        echo "  --watch, -w  Watch for changes and sync continuously"
        echo "  --help, -h   Show this help"
        ;;
    *)
        sync_once
        ;;
esac
