import io
import logging
import zipfile
from pathlib import Path

import cairosvg
from pypdf import PdfWriter, PdfReader
from rmscene import read_tree
from rmc import tree_to_svg

from app.config import ALLOWED_DPI, DEFAULT_DPI

logger = logging.getLogger(__name__)


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
        svg_buffer = io.BytesIO()
        tree_to_svg(tree, svg_buffer)
        return svg_buffer.getvalue().decode("utf-8")
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


def export_pdf(rm_paths: list[Path], dpi: int = DEFAULT_DPI) -> bytes:
    """Render multiple pages into a single merged PDF."""
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
    """Render multiple pages as PNGs and bundle into a ZIP."""
    dpi = validate_dpi(dpi)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, rm_path in enumerate(rm_paths):
            png_bytes = render_page_png(rm_path, dpi)
            zf.writestr(f"page_{i:03d}.png", png_bytes)

    return zip_buffer.getvalue()
