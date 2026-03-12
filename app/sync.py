import logging
import subprocess

from app.config import DATA_PATH, REMARKABLE_HOST, SSH_KEY_PATH, SYNC_TIMEOUT
from app.ssh import has_ssh_key

logger = logging.getLogger(__name__)


class SyncError(Exception):
    pass


def sync_from_remarkable(host: str | None = None) -> tuple[int, str]:
    """Rsync notebooks from reMarkable tablet to local data volume.

    Returns (files_transferred, host_used).
    """
    if not has_ssh_key():
        raise SyncError(
            "SSH key not found. The service generates a key on startup — "
            "check GET /setup/ssh-key for the public key to add to your reMarkable."
        )

    target_host = host or REMARKABLE_HOST
    xochitl_path = f"{DATA_PATH}/xochitl/"
    remote_path = f"root@{target_host}:/home/root/.local/share/remarkable/xochitl/"

    cmd = [
        "rsync",
        "-az",
        "--stats",
        "-e", f"ssh -i {SSH_KEY_PATH} -o StrictHostKeyChecking=no -o ConnectTimeout=10",
        remote_path,
        xochitl_path,
    ]

    logger.info("Starting sync from %s", target_host)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SYNC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise SyncError(f"Sync timed out after {SYNC_TIMEOUT} seconds.")
    except FileNotFoundError:
        raise SyncError("rsync not found. Is it installed?")

    if result.returncode != 0:
        logger.error("rsync failed: %s", result.stderr.strip())
        raise SyncError(f"rsync failed (exit {result.returncode}): {result.stderr.strip()}")

    # Parse "Number of regular files transferred: N" from rsync --stats output
    files_synced = 0
    for line in result.stdout.splitlines():
        if "Number of regular files transferred:" in line:
            try:
                files_synced = int(line.split(":")[-1].strip().replace(",", ""))
            except ValueError:
                pass
            break

    logger.info("Sync complete, %d files transferred from %s.", files_synced, target_host)
    return files_synced, target_host
