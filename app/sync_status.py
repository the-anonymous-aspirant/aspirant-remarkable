import json
import logging
import os
from datetime import datetime, timezone

from app.config import SYNC_STATUS_PATH

logger = logging.getLogger(__name__)


def _read_status() -> dict:
    if not os.path.exists(SYNC_STATUS_PATH):
        return {}
    try:
        with open(SYNC_STATUS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read sync status: %s", exc)
        return {}


def _write_status(status: dict) -> None:
    os.makedirs(os.path.dirname(SYNC_STATUS_PATH), exist_ok=True)
    with open(SYNC_STATUS_PATH, "w") as f:
        json.dump(status, f, indent=2)


def get_status() -> dict:
    """Return current sync status."""
    status = _read_status()
    return {
        "last_sync": status.get("last_sync"),
        "last_sync_direction": status.get("last_sync_direction"),
        "files_synced": status.get("files_synced"),
        "device_ip": status.get("device_ip"),
        "battery": status.get("battery"),
        "device_info_updated": status.get("device_info_updated"),
    }


def update_sync_result(files_synced: int, direction: str) -> None:
    """Record a completed sync event."""
    status = _read_status()
    status["last_sync"] = datetime.now(timezone.utc).isoformat()
    status["last_sync_direction"] = direction
    status["files_synced"] = files_synced
    _write_status(status)


def update_device_info(
    ip: str,
    battery: int | None = None,
    push_files: int | None = None,
    pull_files: int | None = None,
) -> None:
    """Record device info and optional sync results from a push sync."""
    status = _read_status()
    status["device_ip"] = ip
    if battery is not None:
        status["battery"] = battery
    # When the device reports file counts, record as a sync event
    if push_files is not None or pull_files is not None:
        total = (push_files or 0) + (pull_files or 0)
        status["last_sync"] = datetime.now(timezone.utc).isoformat()
        status["last_sync_direction"] = "bidirectional"
        status["files_synced"] = total
    status["device_info_updated"] = datetime.now(timezone.utc).isoformat()
    _write_status(status)
