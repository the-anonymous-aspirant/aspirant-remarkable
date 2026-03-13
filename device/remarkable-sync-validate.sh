#!/bin/bash
# Server-side rsync validation wrapper for reMarkable sync
# Deployed to: /home/aspirant/remarkable-sync-validate.sh
# Referenced in: /home/aspirant/.ssh/authorized_keys (command= directive)
#
# Restricts the reMarkable's SSH key to only run rsync operations
# targeting xochitl/ or to-device/ under /data/aspirant/remarkable/.

ALLOWED_BASE="/data/aspirant/remarkable"
LOG="${ALLOWED_BASE}/sync-access.log"

if [ -z "$SSH_ORIGINAL_COMMAND" ]; then
    echo "Interactive shell not allowed" >&2
    exit 1
fi

# Only allow rsync and device-info POST commands
case "$SSH_ORIGINAL_COMMAND" in
    rsync\ --server*)
        # Extract the path argument (last argument)
        DEST=$(echo "$SSH_ORIGINAL_COMMAND" | rev | cut -d' ' -f1 | rev)
        # Normalize: must be a known subdirectory
        case "$DEST" in
            xochitl/*|to-device/*|xochitl/|to-device/|.)
                echo "$(date -Iseconds) ALLOWED: $SSH_ORIGINAL_COMMAND" >> "$LOG" 2>/dev/null
                cd "$ALLOWED_BASE" && exec $SSH_ORIGINAL_COMMAND
                ;;
            *)
                echo "$(date -Iseconds) DENIED path: $DEST cmd: $SSH_ORIGINAL_COMMAND" >> "$LOG" 2>/dev/null
                echo "Access denied: invalid path" >&2
                exit 1
                ;;
        esac
        ;;
    curl*http://localhost:8086/sync/device-info*)
        # Allow posting device info to the remarkable service (localhost only)
        # Use bash -c to properly handle quoted arguments in the command
        echo "$(date -Iseconds) ALLOWED device-info: $SSH_ORIGINAL_COMMAND" >> "$LOG" 2>/dev/null
        exec bash -c "$SSH_ORIGINAL_COMMAND"
        ;;
    *)
        echo "$(date -Iseconds) DENIED: $SSH_ORIGINAL_COMMAND" >> "$LOG" 2>/dev/null
        echo "Command not allowed" >&2
        exit 1
        ;;
esac
