#!/bin/sh
# Sync reMarkable notebooks to aspirant-cell
# Runs as systemd timer or manually

SERVER_USER="aspirant"
SERVER_HOST="home.the-aspirant.com"
SERVER_PORT="41922"
SSH_KEY="/home/root/.ssh/aspirant_sync_dropbear"
SSH_CMD="dbclient -i ${SSH_KEY} -y -p ${SERVER_PORT}"
XOCHITL_DIR="/home/root/.local/share/remarkable/xochitl"
LOG_FILE="/home/root/sync.log"

log() { echo "$(date +%Y-%m-%dT%H:%M:%S) $1" >> "$LOG_FILE"; }

log "=== Sync started ==="

# 1. Push notebooks to server
log "Pushing xochitl to server..."
PUSH_OUTPUT=$(rsync -az --stats -e "${SSH_CMD}" "${XOCHITL_DIR}/" "${SERVER_USER}@${SERVER_HOST}:xochitl/" 2>&1)
PUSH_RC=$?
PUSH_FILES=$(echo "$PUSH_OUTPUT" | grep "Number of regular files transferred" | awk -F: '{print $2}' | tr -d " ,")
log "Push complete (rc=${PUSH_RC}): ${PUSH_FILES:-0} files transferred"

if [ "$PUSH_RC" -ne 0 ]; then
    log "Push failed: $PUSH_OUTPUT"
fi

# 2. Pull to-device files from server
log "Pulling to-device from server..."
PULL_OUTPUT=$(rsync -az --stats --remove-source-files -e "${SSH_CMD}" "${SERVER_USER}@${SERVER_HOST}:to-device/" "${XOCHITL_DIR}/" 2>&1)
PULL_RC=$?
PULL_FILES=$(echo "$PULL_OUTPUT" | grep "Number of regular files transferred" | awk -F: '{print $2}' | tr -d " ,")
log "Pull complete (rc=${PULL_RC}): ${PULL_FILES:-0} files transferred"

# 3. If new files pulled, signal xochitl to discover them
if [ "${PULL_FILES:-0}" -gt 0 ]; then
    log "Signalling xochitl to discover new files..."
    killall -USR1 xochitl 2>/dev/null && log "xochitl signalled" || log "xochitl signal failed"
fi

# 4. Post device info + sync results via SSH (runs on server, hits localhost)
MY_IP=$(ip addr show wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1)
BATTERY_RAW=$(cat /sys/class/power_supply/max77818_battery/capacity 2>/dev/null)
if [ -n "$BATTERY_RAW" ] && [ "$BATTERY_RAW" -eq "$BATTERY_RAW" ] 2>/dev/null; then
    BATTERY_JSON=$BATTERY_RAW
else
    BATTERY_JSON=null
fi
PAYLOAD="{\"ip\":\"${MY_IP}\",\"battery\":${BATTERY_JSON},\"push_files\":${PUSH_FILES:-0},\"pull_files\":${PULL_FILES:-0}}"
log "Posting device info: ip=${MY_IP} battery=${BATTERY_JSON} push=${PUSH_FILES:-0} pull=${PULL_FILES:-0}"
${SSH_CMD} ${SERVER_USER}@${SERVER_HOST} \
    "curl -sf -o /dev/null -X POST -H 'Content-Type: application/json' -d '${PAYLOAD}' http://localhost:8086/sync/device-info" \
    >/dev/null 2>&1
POST_RC=$?
if [ "$POST_RC" -ne 0 ]; then
    log "Device info POST failed (rc=${POST_RC})"
fi

log "=== Sync finished ==="
