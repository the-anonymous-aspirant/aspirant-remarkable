import os

REMARKABLE_HOST = os.environ.get("REMARKABLE_HOST", "10.11.99.1")
DATA_PATH = os.environ.get("DATA_PATH", "/data/remarkable")
SSH_DIR = os.path.join(DATA_PATH, ".ssh")
SSH_KEY_PATH = os.path.join(SSH_DIR, "id_ed25519")

ALLOWED_DPI = [150, 300, 600, 1200]
DEFAULT_DPI = 300
SYNC_TIMEOUT = 300  # 5 minutes
RENDER_TIMEOUT = 60  # seconds — abort renders that take longer

TO_DEVICE_PATH = os.path.join(DATA_PATH, "to-device")
SYNC_STATUS_PATH = os.path.join(DATA_PATH, "sync_status.json")

REMARKABLE_VERSION = "1.2.0"
SERVICE_NAME = "remarkable"
