import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone

from app.config import TO_DEVICE_PATH

logger = logging.getLogger(__name__)

# File types the reMarkable supports for import.
# Maps file extension (lowercase, with dot) to xochitl fileType value.
SUPPORTED_TYPES: dict[str, str] = {
    ".pdf": "pdf",
    ".epub": "epub",
}


def _ensure_dir() -> str:
    os.makedirs(TO_DEVICE_PATH, exist_ok=True)
    return TO_DEVICE_PATH


def _get_extension(filename: str) -> str:
    """Return the lowercase file extension including the dot."""
    dot = filename.rfind(".")
    if dot == -1:
        return ""
    return filename[dot:].lower()


def is_supported(filename: str) -> bool:
    """Check whether the file extension is supported for upload."""
    return _get_extension(filename) in SUPPORTED_TYPES


def supported_extensions() -> list[str]:
    """Return sorted list of supported extensions for error messages."""
    return sorted(SUPPORTED_TYPES.keys())


def stage_file(
    filename: str,
    file_data: bytes,
    target_folder_id: str | None = None,
) -> dict:
    """Stage a file for syncing to the reMarkable device.

    Generates xochitl-compatible metadata files alongside the document.
    Supports PDF and ePub.
    """
    ext = _get_extension(filename)
    file_type = SUPPORTED_TYPES.get(ext)
    if file_type is None:
        raise ValueError(f"Unsupported file type: {ext}")

    base_dir = _ensure_dir()
    item_id = str(uuid.uuid4())
    now_ms = str(int(datetime.now(timezone.utc).timestamp() * 1000))

    # Strip extension for the visible name
    visible_name = filename
    if ext:
        visible_name = filename[: -len(ext)]

    # Write the document file (keep original extension)
    doc_path = os.path.join(base_dir, f"{item_id}{ext}")
    with open(doc_path, "wb") as f:
        f.write(file_data)

    # Write .metadata (xochitl format)
    metadata = {
        "deleted": False,
        "lastModified": now_ms,
        "lastOpened": "0",
        "lastOpenedPage": 0,
        "metadatamodified": False,
        "modified": False,
        "parent": target_folder_id or "",
        "pinned": False,
        "synced": False,
        "type": "DocumentType",
        "version": 0,
        "visibleName": visible_name,
    }
    metadata_path = os.path.join(base_dir, f"{item_id}.metadata")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Write .content (xochitl format)
    content = {
        "fileType": file_type,
    }
    content_path = os.path.join(base_dir, f"{item_id}.content")
    with open(content_path, "w") as f:
        json.dump(content, f, indent=2)

    return {
        "id": item_id,
        "filename": filename,
        "target_folder_id": target_folder_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "size": len(file_data),
    }


def _find_document_file(base_dir: str, item_id: str) -> str | None:
    """Find the document file for an item by checking supported extensions."""
    for ext in SUPPORTED_TYPES:
        path = os.path.join(base_dir, f"{item_id}{ext}")
        if os.path.exists(path):
            return path
    return None


def list_pending() -> list[dict]:
    """List all staged items awaiting sync to device."""
    base_dir = TO_DEVICE_PATH
    if not os.path.exists(base_dir):
        return []

    items = []
    for metadata_file in sorted(os.listdir(base_dir)):
        if not metadata_file.endswith(".metadata"):
            continue

        item_id = metadata_file[:-9]  # strip .metadata
        metadata_path = os.path.join(base_dir, metadata_file)
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Find the associated document file (PDF, ePub, etc.)
        doc_path = _find_document_file(base_dir, item_id)
        if doc_path is None:
            continue

        # Determine extension from the actual file
        ext = os.path.splitext(doc_path)[1].lower()

        file_size = os.path.getsize(doc_path)
        last_modified = metadata.get("lastModified", "0")
        try:
            ts = datetime.fromtimestamp(int(last_modified) / 1000, tz=timezone.utc)
            created_at = ts.isoformat()
        except (ValueError, OSError):
            created_at = "unknown"

        visible_name = metadata.get("visibleName", item_id)
        parent = metadata.get("parent", "") or None

        items.append({
            "id": item_id,
            "filename": f"{visible_name}{ext}",
            "target_folder_id": parent,
            "created_at": created_at,
            "size": file_size,
        })

    return items


def remove_pending(item_id: str) -> bool:
    """Remove a staged item. Returns True if found and removed."""
    base_dir = TO_DEVICE_PATH
    if not os.path.exists(base_dir):
        return False

    found = False
    # Remove metadata and content sidecar files
    for ext in (".metadata", ".content"):
        path = os.path.join(base_dir, f"{item_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
            found = True

    # Remove the document file (any supported extension)
    for ext in SUPPORTED_TYPES:
        path = os.path.join(base_dir, f"{item_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
            found = True

    # Also remove any directory (e.g. for notebook content)
    dir_path = os.path.join(base_dir, item_id)
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
        found = True

    return found
