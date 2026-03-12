import logging
import os
import subprocess

from app.config import SSH_DIR, SSH_KEY_PATH

logger = logging.getLogger(__name__)


def ensure_ssh_key() -> None:
    """Generate a dedicated Ed25519 key pair if one doesn't exist yet."""
    os.makedirs(SSH_DIR, exist_ok=True)

    if os.path.exists(SSH_KEY_PATH):
        logger.info("SSH key already exists at %s", SSH_KEY_PATH)
        return

    logger.info("Generating dedicated SSH key pair...")
    subprocess.run(
        [
            "ssh-keygen",
            "-t", "ed25519",
            "-f", SSH_KEY_PATH,
            "-N", "",  # no passphrase
            "-C", "remarkable-service",
        ],
        check=True,
        capture_output=True,
    )
    os.chmod(SSH_KEY_PATH, 0o600)
    logger.info("SSH key pair generated at %s", SSH_KEY_PATH)


def has_ssh_key() -> bool:
    """Check if the SSH key pair exists."""
    return os.path.exists(SSH_KEY_PATH)


def get_public_key() -> str:
    """Read and return the public key contents."""
    pub_path = f"{SSH_KEY_PATH}.pub"
    if not os.path.exists(pub_path):
        raise FileNotFoundError("SSH key pair has not been generated yet.")
    with open(pub_path) as f:
        return f.read().strip()
