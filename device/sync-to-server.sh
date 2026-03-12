#!/bin/bash
# sync-to-server.sh — Runs on the reMarkable Paper Pro
#
# 1. Pushes xochitl data to the server via rsync
# 2. Pulls staged files from server to-device directory
# 3. Reports device info (IP, battery) to server
# 4. If new files pulled, signals xochitl to discover them
#
# Designed to run as a systemd timer at midnight.

set -euo pipefail

# ----- Configuration -----
# Override these via environment or edit here
SERVER_HOST="${SYNC_SERVER_HOST:-aspirant.example.com}"
SERVER_PORT="${SYNC_SERVER_PORT:-8085}"
SERVER_DATA_PATH="${SYNC_SERVER_DATA_PATH:-/data/remarkable}"
SERVER_SSH_USER="${SYNC_SERVER_SSH_USER:-root}"
SSH_KEY="/home/root/.ssh/id_ed25519"

XOCHITL_DIR="/home/root/.local/share/remarkable/xochitl"
LOG_TAG="remarkable-sync"

log() {
    logger -t "$LOG_TAG" "$@"
    echo "[$(date -Iseconds)] $*"
}

# ----- Step 1: Push xochitl to server -----
log "Starting push sync to ${SERVER_HOST}..."

PUSH_OUTPUT=$(rsync -az --stats \
    -e "ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=30" \
    "${XOCHITL_DIR}/" \
    "${SERVER_SSH_USER}@${SERVER_HOST}:${SERVER_DATA_PATH}/xochitl/" \
    2>&1) || {
    log "ERROR: Push sync failed: ${PUSH_OUTPUT}"
    exit 1
}

PUSH_FILES=$(echo "$PUSH_OUTPUT" | grep "Number of regular files transferred" | awk '{print $NF}' || echo "0")
log "Push complete: ${PUSH_FILES} files transferred"

# ----- Step 2: Pull to-device files from server -----
log "Pulling to-device files from server..."

PULL_OUTPUT=$(rsync -az --stats --remove-source-files \
    -e "ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=30" \
    "${SERVER_SSH_USER}@${SERVER_HOST}:${SERVER_DATA_PATH}/to-device/" \
    "${XOCHITL_DIR}/" \
    2>&1) || {
    log "WARNING: Pull sync failed (non-fatal): ${PULL_OUTPUT}"
    PULL_FILES=0
}

PULL_FILES=$(echo "$PULL_OUTPUT" | grep "Number of regular files transferred" | awk '{print $NF}' || echo "0")
log "Pull complete: ${PULL_FILES} files transferred"

# ----- Step 3: Report device info -----
DEVICE_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || echo "unknown")

BATTERY_LEVEL=""
if [ -f /sys/class/power_supply/bq27441-0/capacity ]; then
    BATTERY_LEVEL=$(cat /sys/class/power_supply/bq27441-0/capacity)
elif [ -f /sys/class/power_supply/max77818_battery/capacity ]; then
    BATTERY_LEVEL=$(cat /sys/class/power_supply/max77818_battery/capacity)
fi

if [ -n "$BATTERY_LEVEL" ]; then
    PAYLOAD="{\"ip\": \"${DEVICE_IP}\", \"battery\": ${BATTERY_LEVEL}}"
else
    PAYLOAD="{\"ip\": \"${DEVICE_IP}\"}"
fi

log "Reporting device info: ${PAYLOAD}"

# POST directly to the remarkable service (not through auth proxy)
curl -sf -X POST \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
    "http://${SERVER_HOST}:${SERVER_PORT}/sync/device-info" \
    >/dev/null 2>&1 || log "WARNING: Failed to report device info (non-fatal)"

# ----- Step 4: Signal xochitl if new files pulled -----
if [ "${PULL_FILES}" -gt 0 ] 2>/dev/null; then
    log "New files pulled, signaling xochitl to discover them..."
    killall -USR1 xochitl 2>/dev/null || log "WARNING: Could not signal xochitl"
fi

log "Sync complete (push: ${PUSH_FILES}, pull: ${PULL_FILES})"
