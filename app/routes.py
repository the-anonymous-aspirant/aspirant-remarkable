import asyncio
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from app.config import ALLOWED_DPI, DEFAULT_DPI, ALLOWED_QUALITY, DEFAULT_QUALITY, SERVICE_NAME, REMARKABLE_VERSION, DATA_PATH, RENDER_TIMEOUT
from app.schemas import (
    HealthResponse, SyncRequest, SyncResponse, NotebookSummary, NotebookDetail,
    FolderSummary, FolderTreeNode, SyncStatusResponse, DeviceInfoRequest, ToDeviceItem,
)
from app import parser, sync, renderer, ssh, sync_status, to_device
from app.parser import NotebookNotFoundError, PageNotFoundError
from app.sync import SyncError
from app.renderer import RenderError

logger = logging.getLogger(__name__)
router = APIRouter()

# Track the current render task so new requests can cancel in-flight ones.
_current_render: asyncio.Task | None = None


async def _run_render(fn, *args):
    """Run a render function in a thread with timeout and cancellation.

    Only one render runs at a time — starting a new one cancels any in-flight
    render so they don't compete for CPU.
    """
    global _current_render

    # Cancel any in-flight render
    if _current_render is not None and not _current_render.done():
        _current_render.cancel()

    task = asyncio.ensure_future(
        asyncio.wait_for(
            asyncio.to_thread(fn, *args),
            timeout=RENDER_TIMEOUT,
        )
    )
    _current_render = task

    try:
        return await task
    except asyncio.TimeoutError:
        raise RenderError(f"Rendering timed out after {RENDER_TIMEOUT} seconds. Try a lower DPI or simpler page.")
    except asyncio.CancelledError:
        raise RenderError("Render cancelled by a newer request.")


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@router.get("/health")
def health_check():
    checks = {}

    # Check rmscene importable
    try:
        import rmscene  # noqa: F401
        checks["rmscene"] = "available"
    except Exception:
        checks["rmscene"] = "unavailable"

    # Check rmc importable
    try:
        import rmc  # noqa: F401
        checks["rmc"] = "available"
    except Exception:
        checks["rmc"] = "unavailable"

    # Check data volume writable
    try:
        import os
        test_file = os.path.join(DATA_PATH, ".write_test")
        os.makedirs(DATA_PATH, exist_ok=True)
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        checks["data_volume"] = "writable"
    except Exception:
        checks["data_volume"] = "not_writable"

    # Check SSH key exists
    checks["ssh_key"] = "available" if ssh.has_ssh_key() else "not_generated"

    all_ok = all(
        v in ("available", "writable") for v in checks.values()
    )

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        service=SERVICE_NAME,
        version=REMARKABLE_VERSION,
        checks=checks,
    )


@router.get("/setup/ssh-key")
def get_ssh_key():
    """Return the service's public SSH key for adding to the reMarkable."""
    try:
        public_key = ssh.get_public_key()
    except FileNotFoundError:
        return _error(503, "service_unavailable", "SSH key not yet generated. Restart the service.")

    return {
        "public_key": public_key,
        "instructions": (
            "Add this public key to your reMarkable tablet:\n"
            "  ssh root@10.11.99.1 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys' "
            "<<< '<paste public_key here>'"
        ),
    }


@router.post("/sync")
def sync_notebooks(body: SyncRequest = SyncRequest()):
    try:
        files_synced, host_used = sync.sync_from_remarkable(host=body.host)
    except SyncError as exc:
        return _error(503, "service_unavailable", str(exc))

    sync_status.update_sync_result(files_synced, "pull")

    return SyncResponse(
        status="ok",
        message=f"Sync complete. {files_synced} files transferred.",
        host=host_used,
        files_synced=files_synced,
    )


@router.get("/notebooks")
def list_notebooks(parent_id: str = Query(None, description="Filter by parent folder ID")):
    if parent_id is not None:
        notebooks = parser.list_notebooks(parent_id=parent_id)
    else:
        notebooks = parser.list_notebooks()
    return [
        NotebookSummary(**nb) for nb in notebooks
    ]


@router.get("/folders")
def list_folders():
    folders = parser.list_folders()
    return [
        FolderSummary(
            id=f["id"], name=f["name"],
            parent_id=f["parent_id"], last_modified=f["last_modified"],
        )
        for f in folders
    ]


@router.get("/folders/{folder_id}/contents")
def get_folder_contents(folder_id: str):
    contents = parser.list_folder_contents(folder_id)
    return contents


@router.get("/tree")
def get_tree():
    return parser.get_folder_tree()


@router.get("/notebooks/{notebook_id}")
def get_notebook(notebook_id: str):
    try:
        nb = parser.get_notebook(notebook_id)
    except NotebookNotFoundError:
        return _error(404, "not_found", f"Notebook {notebook_id} not found.")

    return NotebookDetail(**nb)


@router.get("/notebooks/{notebook_id}/pages/{page_num}/render")
async def render_page(
    notebook_id: str,
    page_num: int,
    format: str = Query("png", pattern="^(png|pdf)$"),
    dpi: int = Query(DEFAULT_DPI),
    quality: str = Query(DEFAULT_QUALITY),
):
    if dpi not in ALLOWED_DPI:
        return _error(
            400, "validation_error",
            f"Invalid DPI: {dpi}. Allowed values: {ALLOWED_DPI}",
        )
    if quality not in ALLOWED_QUALITY:
        return _error(
            400, "validation_error",
            f"Invalid quality: {quality}. Allowed values: {ALLOWED_QUALITY}",
        )

    try:
        source = parser.get_page_source(notebook_id, page_num)
    except NotebookNotFoundError:
        return _error(404, "not_found", f"Notebook {notebook_id} not found.")
    except PageNotFoundError as exc:
        return _error(400, "validation_error", str(exc))

    try:
        if source["type"] == "rm":
            if format == "png":
                data = await _run_render(renderer.render_page_png, source["path"], dpi, quality)
                return Response(content=data, media_type="image/png")
            else:
                data = await _run_render(renderer.render_page_pdf, source["path"], dpi, quality)
                return Response(content=data, media_type="application/pdf")
        else:
            # PDF-backed page — quality doesn't apply
            if format == "png":
                data = await _run_render(renderer.render_pdf_page_png, source["path"], source["pdf_page"], dpi)
                return Response(content=data, media_type="image/png")
            else:
                data = await _run_render(renderer.render_pdf_page_pdf, source["path"], source["pdf_page"])
                return Response(content=data, media_type="application/pdf")
    except RenderError as exc:
        return _error(500, "internal_error", str(exc))


@router.get("/notebooks/{notebook_id}/export")
async def export_notebook(
    notebook_id: str,
    format: str = Query("pdf", pattern="^(pdf|png)$"),
    dpi: int = Query(DEFAULT_DPI),
    quality: str = Query(DEFAULT_QUALITY),
    pages: str = Query(None, description="Comma-separated page numbers (e.g., 0,1,2). Omit for all pages."),
):
    if dpi not in ALLOWED_DPI:
        return _error(
            400, "validation_error",
            f"Invalid DPI: {dpi}. Allowed values: {ALLOWED_DPI}",
        )
    if quality not in ALLOWED_QUALITY:
        return _error(
            400, "validation_error",
            f"Invalid quality: {quality}. Allowed values: {ALLOWED_QUALITY}",
        )

    try:
        nb = parser.get_notebook(notebook_id)
    except NotebookNotFoundError:
        return _error(404, "not_found", f"Notebook {notebook_id} not found.")

    # Resolve page numbers
    if pages is not None:
        try:
            page_nums = [int(p.strip()) for p in pages.split(",")]
        except ValueError:
            return _error(400, "validation_error", "Invalid page numbers. Use comma-separated integers.")
    else:
        page_nums = nb["pages"]

    # Resolve page sources
    page_sources = []
    for page_num in page_nums:
        try:
            page_sources.append(parser.get_page_source(notebook_id, page_num))
        except (NotebookNotFoundError, PageNotFoundError) as exc:
            return _error(400, "validation_error", str(exc))

    if not page_sources:
        return _error(400, "validation_error", "No pages to export.")

    try:
        if format == "pdf":
            data = await _run_render(renderer.export_mixed_pdf, page_sources, dpi, quality)
            filename = f"{nb['name']}.pdf"
            return Response(
                content=data,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        else:
            data = await _run_render(renderer.export_mixed_zip, page_sources, dpi, quality)
            filename = f"{nb['name']}.zip"
            return Response(
                content=data,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
    except RenderError as exc:
        return _error(500, "internal_error", str(exc))


# -------------------------------------------------------------------
# Sync status endpoints
# -------------------------------------------------------------------

@router.get("/sync/status")
def get_sync_status():
    status = sync_status.get_status()
    return SyncStatusResponse(**status)


@router.post("/sync/device-info")
def post_device_info(body: DeviceInfoRequest):
    sync_status.update_device_info(
        body.ip,
        battery=body.battery,
        push_files=body.push_files,
        pull_files=body.pull_files,
    )
    return {"status": "ok"}


# -------------------------------------------------------------------
# To-device (bidirectional sync) endpoints
# -------------------------------------------------------------------

@router.post("/to-device/upload")
async def upload_to_device(
    request: Request,
):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return _error(400, "validation_error", "Request must be multipart/form-data")

    form = await request.form()
    file = form.get("file")
    if file is None:
        return _error(400, "validation_error", "No file provided")

    filename = file.filename or ""
    if not to_device.is_supported(filename):
        exts = ", ".join(to_device.supported_extensions())
        return _error(400, "validation_error", f"Unsupported file type. Supported: {exts}")

    file_data = await file.read()
    if not file_data:
        return _error(400, "validation_error", "File is empty")

    target_folder_id = form.get("target_folder_id")
    if isinstance(target_folder_id, str) and target_folder_id.strip() == "":
        target_folder_id = None

    try:
        item = to_device.stage_file(filename, file_data, target_folder_id)
    except Exception as exc:
        logger.error("Failed to stage file: %s", exc)
        return _error(500, "internal_error", str(exc))

    return ToDeviceItem(**item)


@router.get("/to-device/pending")
def list_pending():
    items = to_device.list_pending()
    return [ToDeviceItem(**item) for item in items]


@router.delete("/to-device/{item_id}")
def delete_pending(item_id: str):
    removed = to_device.remove_pending(item_id)
    if not removed:
        return _error(404, "not_found", f"Pending item {item_id} not found")
    return {"status": "ok"}
