import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_PATH

logger = logging.getLogger(__name__)


class NotebookNotFoundError(Exception):
    pass


class PageNotFoundError(Exception):
    pass


def _xochitl_path() -> Path:
    return Path(DATA_PATH) / "xochitl"


def _read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


class FolderNotFoundError(Exception):
    pass


def _parse_timestamp(raw: str) -> str:
    """Convert reMarkable epoch-millis string to ISO-8601."""
    try:
        ts = datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
        return ts.isoformat()
    except (ValueError, OSError):
        return "unknown"


def _parse_item(item_id: str, metadata: dict) -> dict:
    """Extract common fields from any xochitl item (document or folder)."""
    return {
        "id": item_id,
        "name": metadata.get("visibleName", item_id),
        "type": metadata.get("type", ""),
        "parent_id": metadata.get("parent", "") or None,
        "last_modified": _parse_timestamp(metadata.get("lastModified", "0")),
    }


def list_all_items() -> list[dict]:
    """Return all non-deleted items (documents and folders) with metadata."""
    xochitl = _xochitl_path()
    if not xochitl.exists():
        return []

    items = []
    for metadata_file in xochitl.glob("*.metadata"):
        item_id = metadata_file.stem
        try:
            metadata = _read_json(metadata_file)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping %s: %s", item_id, exc)
            continue

        if metadata.get("deleted", False):
            continue

        item = _parse_item(item_id, metadata)

        if metadata.get("type") == "DocumentType":
            page_ids = _get_page_ids(item_id)
            item["page_count"] = len(page_ids)
        else:
            item["page_count"] = 0

        items.append(item)

    items.sort(key=lambda i: i["last_modified"], reverse=True)
    return items


def list_folders() -> list[dict]:
    """Return all CollectionType items (folders)."""
    return [
        item for item in list_all_items()
        if item["type"] == "CollectionType"
    ]


def list_folder_contents(folder_id: str | None) -> list[dict]:
    """Return items whose parent matches the given folder_id (None = root)."""
    return [
        item for item in list_all_items()
        if item["parent_id"] == folder_id
    ]


def get_folder_tree() -> list[dict]:
    """Build a nested tree from flat parent references. Returns root-level nodes."""
    items = list_all_items()
    by_id: dict[str, dict] = {}
    for item in items:
        item["children"] = []
        by_id[item["id"]] = item

    roots: list[dict] = []
    for item in items:
        parent = item["parent_id"]
        if not parent:
            # True root items (parent_id is None or empty)
            roots.append(item)
        elif parent in by_id:
            # Item belongs to a known, non-deleted folder
            by_id[parent]["children"].append(item)
        # else: parent is a deleted/unknown folder (e.g. "trash") — skip

    return roots


def list_notebooks(parent_id: str | None = ...) -> list[dict]:
    """List all notebooks with name, page count, and last modified time.

    If parent_id is provided, filter to notebooks in that folder (None = root).
    If parent_id is the sentinel (default), return all notebooks.
    """
    xochitl = _xochitl_path()
    if not xochitl.exists():
        return []

    notebooks = []
    for metadata_file in xochitl.glob("*.metadata"):
        notebook_id = metadata_file.stem
        try:
            metadata = _read_json(metadata_file)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping %s: %s", notebook_id, exc)
            continue

        if metadata.get("type") != "DocumentType":
            continue
        if metadata.get("deleted", False):
            continue

        item_parent = metadata.get("parent", "") or None

        # Filter by parent_id when specified
        if parent_id is not ...:
            if item_parent != parent_id:
                continue

        name = metadata.get("visibleName", notebook_id)
        last_modified_iso = _parse_timestamp(metadata.get("lastModified", "0"))
        page_ids = _get_page_ids(notebook_id)

        notebooks.append({
            "id": notebook_id,
            "name": name,
            "page_count": len(page_ids),
            "last_modified": last_modified_iso,
            "parent_id": item_parent,
        })

    notebooks.sort(key=lambda n: n["last_modified"], reverse=True)
    return notebooks


def get_notebook(notebook_id: str) -> dict:
    """Get notebook detail with page list."""
    xochitl = _xochitl_path()
    metadata_path = xochitl / f"{notebook_id}.metadata"

    if not metadata_path.exists():
        raise NotebookNotFoundError(f"Notebook {notebook_id} not found.")

    metadata = _read_json(metadata_path)
    name = metadata.get("visibleName", notebook_id)
    last_modified = metadata.get("lastModified", "0")
    try:
        ts = datetime.fromtimestamp(int(last_modified) / 1000, tz=timezone.utc)
        last_modified_iso = ts.isoformat()
    except (ValueError, OSError):
        last_modified_iso = "unknown"

    page_ids = _get_page_ids(notebook_id)

    return {
        "id": notebook_id,
        "name": name,
        "page_count": len(page_ids),
        "last_modified": last_modified_iso,
        "pages": list(range(len(page_ids))),
    }


def _get_page_ids(notebook_id: str) -> list[str]:
    """Read page IDs from .content file."""
    xochitl = _xochitl_path()
    content_path = xochitl / f"{notebook_id}.content"

    if not content_path.exists():
        return []

    try:
        content = _read_json(content_path)
    except (json.JSONDecodeError, OSError):
        return []

    # v6 format: cPages.pages[] has id field
    cpages = content.get("cPages", {})
    if isinstance(cpages, dict):
        pages = cpages.get("pages", [])
        return [p.get("id", "") for p in pages if isinstance(p, dict)]

    # Fallback: pages array at top level
    pages = content.get("pages", [])
    if isinstance(pages, list):
        return pages

    return []


def get_page_source(notebook_id: str, page_num: int) -> dict:
    """Resolve the source for rendering a specific page.

    Returns a dict with:
      - "type": "rm" or "pdf"
      - "path": Path to .rm file or .pdf file
      - "pdf_page": (only for type "pdf") zero-based page index within the PDF
    """
    page_ids = _get_page_ids(notebook_id)
    if not page_ids:
        raise NotebookNotFoundError(f"Notebook {notebook_id} not found or has no pages.")

    if page_num < 0 or page_num >= len(page_ids):
        raise PageNotFoundError(
            f"Page {page_num} out of range. Notebook has {len(page_ids)} pages (0-{len(page_ids) - 1})."
        )

    page_id = page_ids[page_num]
    xochitl = _xochitl_path()

    # Check for .rm annotation file first
    rm_path = xochitl / notebook_id / f"{page_id}.rm"
    if rm_path.exists():
        return {"type": "rm", "path": rm_path}

    # Check for a backing PDF
    pdf_path = xochitl / f"{notebook_id}.pdf"
    if pdf_path.exists():
        return {"type": "pdf", "path": pdf_path, "pdf_page": page_num}

    raise PageNotFoundError(
        f"No renderable source for page {page_num}: no .rm file and no backing PDF."
    )


def get_rm_path(notebook_id: str, page_num: int) -> Path:
    """Resolve the .rm file path for a specific page number.

    Kept for backward compatibility with export functions.
    Raises PageNotFoundError if the page has no .rm file.
    """
    source = get_page_source(notebook_id, page_num)
    if source["type"] != "rm":
        raise PageNotFoundError(
            f"Page {page_num} is PDF-backed and has no .rm annotations."
        )
    return source["path"]
