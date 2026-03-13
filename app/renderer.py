import io
import logging
import zipfile
from pathlib import Path

import cairosvg
import fitz  # pymupdf
from pypdf import PdfWriter, PdfReader
from rmscene import read_tree
from rmc import tree_to_svg
from rmc.exporters import writing_tools

from app.config import ALLOWED_DPI, DEFAULT_DPI

logger = logging.getLogger(__name__)

# Patch rmc's color palette to support newer reMarkable Paper Pro colors.
# The rmc library (0.3.0) is missing color 9 and may lack future additions.
_EXTRA_COLORS = {
    9: (255, 175, 99),   # Orange (Paper Pro highlighter)
}
for _cid, _rgb in _EXTRA_COLORS.items():
    if _cid not in writing_tools.RM_PALETTE:
        writing_tools.RM_PALETTE[_cid] = _rgb

# Wrap the palette so unknown color IDs fall back to black instead of crashing.
_original_palette = writing_tools.RM_PALETTE


class _FallbackPalette(dict):
    def __missing__(self, key):
        logger.warning("Unknown reMarkable color ID %d, falling back to black", key)
        return (0, 0, 0)


writing_tools.RM_PALETTE = _FallbackPalette(_original_palette)


class RenderError(Exception):
    pass


def validate_dpi(dpi: int) -> int:
    if dpi not in ALLOWED_DPI:
        raise ValueError(
            f"Invalid DPI: {dpi}. Allowed values: {ALLOWED_DPI}"
        )
    return dpi


def render_page_svg(rm_path: Path) -> str:
    """Parse .rm file and convert to SVG string."""
    try:
        with open(rm_path, "rb") as f:
            tree = read_tree(f)
        svg_buffer = io.StringIO()
        tree_to_svg(tree, svg_buffer)
        return svg_buffer.getvalue()
    except Exception as exc:
        raise RenderError(f"Failed to render SVG from {rm_path}: {exc}")


def render_page_png(rm_path: Path, dpi: int = DEFAULT_DPI) -> bytes:
    """Render .rm file to PNG at specified DPI."""
    dpi = validate_dpi(dpi)
    svg_str = render_page_svg(rm_path)

    # reMarkable display is 1404x1872 pixels at ~226 DPI
    # Scale factor relative to native resolution
    scale = dpi / 226.0

    try:
        png_bytes = cairosvg.svg2png(
            bytestring=svg_str.encode("utf-8"),
            scale=scale,
        )
        return png_bytes
    except Exception as exc:
        raise RenderError(f"Failed to convert SVG to PNG: {exc}")


def render_page_pdf(rm_path: Path, dpi: int = DEFAULT_DPI) -> bytes:
    """Render .rm file to a single-page PDF at specified DPI."""
    dpi = validate_dpi(dpi)
    svg_str = render_page_svg(rm_path)

    scale = dpi / 226.0

    try:
        pdf_bytes = cairosvg.svg2pdf(
            bytestring=svg_str.encode("utf-8"),
            scale=scale,
        )
        return pdf_bytes
    except Exception as exc:
        raise RenderError(f"Failed to convert SVG to PDF: {exc}")


def render_pdf_page_png(pdf_path: Path, page_num: int, dpi: int = DEFAULT_DPI) -> bytes:
    """Render a single page from a backing PDF as PNG using PyMuPDF."""
    dpi = validate_dpi(dpi)
    try:
        doc = fitz.open(str(pdf_path))
        if page_num >= len(doc):
            raise RenderError(
                f"PDF page {page_num} out of range (PDF has {len(doc)} pages)."
            )
        page = doc[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(f"Failed to render PDF page {page_num}: {exc}")


def render_pdf_page_pdf(pdf_path: Path, page_num: int) -> bytes:
    """Extract a single page from a backing PDF as a standalone PDF."""
    try:
        reader = PdfReader(str(pdf_path))
        if page_num >= len(reader.pages):
            raise RenderError(
                f"PDF page {page_num} out of range (PDF has {len(reader.pages)} pages)."
            )
        writer = PdfWriter()
        writer.add_page(reader.pages[page_num])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(f"Failed to extract PDF page {page_num}: {exc}")


def export_pdf(rm_paths: list[Path], dpi: int = DEFAULT_DPI) -> bytes:
    """Render multiple .rm pages into a single merged PDF."""
    dpi = validate_dpi(dpi)
    writer = PdfWriter()

    for rm_path in rm_paths:
        page_pdf = render_page_pdf(rm_path, dpi)
        reader = PdfReader(io.BytesIO(page_pdf))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def export_pngs_zip(rm_paths: list[Path], dpi: int = DEFAULT_DPI) -> bytes:
    """Render multiple .rm pages as PNGs and bundle into a ZIP."""
    dpi = validate_dpi(dpi)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, rm_path in enumerate(rm_paths):
            png_bytes = render_page_png(rm_path, dpi)
            zf.writestr(f"page_{i:03d}.png", png_bytes)

    return zip_buffer.getvalue()


def export_mixed_pdf(page_sources: list[dict], dpi: int = DEFAULT_DPI) -> bytes:
    """Export pages (mix of .rm and PDF-backed) into a single merged PDF."""
    dpi = validate_dpi(dpi)
    writer = PdfWriter()

    for source in page_sources:
        if source["type"] == "rm":
            page_pdf = render_page_pdf(source["path"], dpi)
            reader = PdfReader(io.BytesIO(page_pdf))
        else:
            page_pdf = render_pdf_page_pdf(source["path"], source["pdf_page"])
            reader = PdfReader(io.BytesIO(page_pdf))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def export_mixed_zip(page_sources: list[dict], dpi: int = DEFAULT_DPI) -> bytes:
    """Export pages (mix of .rm and PDF-backed) as PNGs in a ZIP."""
    dpi = validate_dpi(dpi)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, source in enumerate(page_sources):
            if source["type"] == "rm":
                png_bytes = render_page_png(source["path"], dpi)
            else:
                png_bytes = render_pdf_page_png(source["path"], source["pdf_page"], dpi)
            zf.writestr(f"page_{i:03d}.png", png_bytes)

    return zip_buffer.getvalue()
