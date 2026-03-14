"""Variable-width ribbon SVG exporter for reMarkable .rm files.

Produces higher-quality SVG than the rmc library's polyline renderer by
computing per-point stroke width and building filled ribbon paths instead
of fixed-width polylines.
"""

import io
import logging
import math
import string
import typing as tp

from rmscene import CrdtId, SceneTree
from rmscene import scene_items as si
from rmscene.text import TextDocument

from rmc.exporters.writing_tools import (
    Pen,
    Ballpoint,
    Pencil,
    Brush,
    Marker,
    Calligraphy,
)

logger = logging.getLogger(__name__)

# --- Screen / coordinate constants (identical to rmc) ---

SCREEN_WIDTH = 1404
SCREEN_HEIGHT = 1872
SCREEN_DPI = 226
SCALE = 72.0 / SCREEN_DPI


def _scale(v: float) -> float:
    return v * SCALE


_xx = _scale
_yy = _scale

# --- SVG boilerplate ---

_SVG_HEADER = string.Template(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'height="$height" width="$width" viewBox="$viewbox">'
)

# --- Text constants (from rmc) ---

_TEXT_TOP_Y = -88
_LINE_HEIGHTS = {
    si.ParagraphStyle.PLAIN: 70,
    si.ParagraphStyle.BULLET: 35,
    si.ParagraphStyle.BULLET2: 35,
    si.ParagraphStyle.BOLD: 70,
    si.ParagraphStyle.HEADING: 150,
    si.ParagraphStyle.CHECKBOX: 35,
    si.ParagraphStyle.CHECKBOX_CHECKED: 35,
}

# Pen classes that benefit from variable-width ribbon rendering.
# All other pens (Fineliner, MechanicalPencil, Highlighter, Shader,
# Eraser, EraseArea) fall back to the standard polyline approach.
_RIBBON_PEN_TYPES = (Ballpoint, Pencil, Brush, Marker, Calligraphy)

# Map pen types to SVG filter IDs for texture effects.
_PEN_FILTER = {
    Pencil: "pencil-grain",
    Brush: "brush-bristle",
    Ballpoint: "ballpoint-ink",
    Calligraphy: "calligraphy-ink",
}


# ====================================================================
# Public API
# ====================================================================


def tree_to_svg_fine(tree: SceneTree, output: io.StringIO) -> None:
    """Convert a SceneTree to SVG with variable-width ribbon strokes.

    Drop-in alternative to ``rmc.tree_to_svg`` for higher quality output.
    """
    anchor_pos = _build_anchor_pos(tree.root_text)

    x_min, x_max, y_min, y_max = _get_bounding_box(tree.root, anchor_pos)

    width_pt = _xx(x_max - x_min + 1)
    height_pt = _yy(y_max - y_min + 1)

    output.write(_SVG_HEADER.substitute(
        width=width_pt,
        height=height_pt,
        viewbox=f"{_xx(x_min)} {_yy(y_min)} {width_pt} {height_pt}",
    ))
    output.write("\n")

    # Defs — pen texture filters
    output.write("<defs>\n")
    # Pencil: dual-layer grain (coarse paper texture + fine graphite)
    # with slight edge displacement for natural graphite-on-paper look
    output.write(
        '  <filter id="pencil-grain" x="-5%" y="-5%" width="110%" height="110%">\n'
        '    <feTurbulence type="fractalNoise" baseFrequency="0.5" '
        'numOctaves="4" seed="1" result="coarse"/>\n'
        '    <feTurbulence type="fractalNoise" baseFrequency="1.5" '
        'numOctaves="2" seed="2" result="fine"/>\n'
        '    <feMerge result="grain">\n'
        '      <feMergeNode in="coarse"/>\n'
        '      <feMergeNode in="fine"/>\n'
        '    </feMerge>\n'
        '    <feDisplacementMap in="SourceGraphic" in2="grain" '
        'scale="1.2" xChannelSelector="R" yChannelSelector="G" result="displaced"/>\n'
        '    <feComposite in="displaced" in2="coarse" operator="in"/>\n'
        "  </filter>\n"
    )
    # Brush: elongated bristle streaks via directional turbulence
    # + displacement for edge irregularity
    output.write(
        '  <filter id="brush-bristle" x="-5%" y="-5%" width="110%" height="110%">\n'
        '    <feTurbulence type="turbulence" baseFrequency="0.03 0.4" '
        'numOctaves="3" seed="3" result="bristle"/>\n'
        '    <feDisplacementMap in="SourceGraphic" in2="bristle" '
        'scale="2.0" xChannelSelector="R" yChannelSelector="G" result="displaced"/>\n'
        '    <feComposite in="displaced" in2="bristle" operator="in" result="textured"/>\n'
        '    <feBlend in="SourceGraphic" in2="textured" mode="multiply"/>\n'
        "  </filter>\n"
    )
    # Ballpoint: subtle ink density variation
    output.write(
        '  <filter id="ballpoint-ink" x="0%" y="0%" width="100%" height="100%">\n'
        '    <feTurbulence type="fractalNoise" baseFrequency="1.8" '
        'numOctaves="3" seed="4" result="ink"/>\n'
        '    <feColorMatrix in="ink" type="saturate" values="0" result="grey"/>\n'
        '    <feComponentTransfer in="grey" result="mask">\n'
        '      <feFuncA type="linear" slope="0.3" intercept="0.7"/>\n'
        '    </feComponentTransfer>\n'
        '    <feComposite in="SourceGraphic" in2="mask" operator="in"/>\n'
        "  </filter>\n"
    )
    # Calligraphy: ink pooling at edges (darker edges, lighter centre)
    output.write(
        '  <filter id="calligraphy-ink" x="-2%" y="-2%" width="104%" height="104%">\n'
        '    <feMorphology in="SourceGraphic" operator="erode" radius="0.3" result="inner"/>\n'
        '    <feGaussianBlur in="inner" stdDeviation="0.5" result="blurred"/>\n'
        '    <feBlend in="SourceGraphic" in2="blurred" mode="darken"/>\n'
        "  </filter>\n"
    )
    output.write("</defs>\n")

    output.write('\t<g id="p1" style="display:inline">\n')

    if tree.root_text is not None:
        _draw_text(tree.root_text, output)

    _draw_group(tree.root, output, anchor_pos)

    output.write("\t</g>\n")
    output.write("</svg>\n")


# ====================================================================
# Tree traversal helpers (mirror rmc structure)
# ====================================================================


def _build_anchor_pos(text: tp.Optional[si.Text]) -> dict:
    anchor_pos: dict = {
        CrdtId(0, 281474976710654): 100,
        CrdtId(0, 281474976710655): 100,
    }
    if text is not None:
        doc = TextDocument.from_scene_item(text)
        ypos = text.pos_y + _TEXT_TOP_Y
        for p in doc.contents:
            anchor_pos[p.start_id] = ypos
            for subp in p.contents:
                for k in subp.i:
                    anchor_pos[k] = ypos
            ypos += _LINE_HEIGHTS.get(p.style.value, 70)
    return anchor_pos


def _get_anchor(item: si.Group, anchor_pos: dict) -> tuple[float, float]:
    ax = 0.0
    ay = 0.0
    if item.anchor_id is not None:
        assert item.anchor_origin_x is not None
        ax = item.anchor_origin_x.value
        if item.anchor_id.value in anchor_pos:
            ay = anchor_pos[item.anchor_id.value]
    return ax, ay


def _get_bounding_box(
    item: si.Group,
    anchor_pos: dict,
    default: tuple = (-SCREEN_WIDTH // 2, SCREEN_WIDTH // 2, 0, SCREEN_HEIGHT),
) -> tuple:
    x_min, x_max, y_min, y_max = default
    for child_id in item.children:
        child = item.children[child_id]
        if isinstance(child, si.Group):
            ax, ay = _get_anchor(child, anchor_pos)
            cx_min, cx_max, cy_min, cy_max = _get_bounding_box(
                child, anchor_pos, (0, 0, 0, 0)
            )
            x_min = min(x_min, cx_min + ax)
            x_max = max(x_max, cx_max + ax)
            y_min = min(y_min, cy_min + ay)
            y_max = max(y_max, cy_max + ay)
        elif isinstance(child, si.Line):
            x_min = min([x_min] + [p.x for p in child.points])
            x_max = max([x_max] + [p.x for p in child.points])
            y_min = min([y_min] + [p.y for p in child.points])
            y_max = max([y_max] + [p.y for p in child.points])
    return x_min, x_max, y_min, y_max


def _draw_group(item: si.Group, output: io.StringIO, anchor_pos: dict) -> None:
    ax, ay = _get_anchor(item, anchor_pos)
    output.write(
        f'\t\t<g id="{item.node_id}" '
        f'transform="translate({_xx(ax)}, {_yy(ay)})">\n'
    )
    for child_id in item.children:
        child = item.children[child_id]
        if isinstance(child, si.Group):
            _draw_group(child, output, anchor_pos)
        elif isinstance(child, si.Line):
            _draw_stroke(child, output)
    output.write("\t\t</g>\n")


# ====================================================================
# Stroke rendering
# ====================================================================


def _draw_stroke(item: si.Line, output: io.StringIO) -> None:
    pen = Pen.create(item.tool.value, item.color.value, item.thickness_scale)

    if len(item.points) < 2:
        return

    if isinstance(pen, _RIBBON_PEN_TYPES):
        _draw_stroke_ribbon(item, pen, output)
    else:
        _draw_stroke_polyline(item, pen, output)


def _draw_stroke_polyline(item: si.Line, pen: Pen, output: io.StringIO) -> None:
    """Polyline fallback — identical to rmc for Highlighter/Shader/Eraser."""
    last_xpos = -1.0
    last_ypos = -1.0
    last_width = segment_width = 0

    for pid, point in enumerate(item.points):
        xpos, ypos = point.x, point.y
        if pid % pen.segment_length == 0:
            if last_xpos != -1.0:
                output.write('"/>\n')
            segment_color = pen.get_segment_color(
                point.speed, point.direction, point.width, point.pressure, last_width
            )
            segment_width = pen.get_segment_width(
                point.speed, point.direction, point.width, point.pressure, last_width
            )
            segment_opacity = pen.get_segment_opacity(
                point.speed, point.direction, point.width, point.pressure, last_width
            )
            output.write("\t\t\t<polyline ")
            output.write(
                f'style="fill:none; stroke:{segment_color}; '
                f"stroke-width:{_scale(segment_width):.3f}; "
                f'opacity:{segment_opacity}" '
            )
            output.write(f'stroke-linecap="{pen.stroke_linecap}" ')
            output.write('points="')
            if last_xpos != -1.0:
                output.write(f"{_xx(last_xpos):.3f},{_yy(last_ypos):.3f} ")
        last_xpos = xpos
        last_ypos = ypos
        last_width = segment_width
        output.write(f"{_xx(xpos):.3f},{_yy(ypos):.3f} ")

    output.write('" />\n')


def _draw_stroke_ribbon(item: si.Line, pen: Pen, output: io.StringIO) -> None:
    """Variable-width ribbon renderer — core of the fine-quality mode."""
    points = item.points

    # Per-point widths
    widths = _compute_point_widths(points, pen)
    widths = _smooth_widths(widths)

    # Per-point color / opacity
    colors, opacities = _compute_point_styles(points, pen)

    # Determine whether style varies across the stroke
    color_varies = len(set(colors)) > 1
    opacity_varies = len(set(opacities)) > 1

    filter_id = _PEN_FILTER.get(type(pen))

    if color_varies or opacity_varies:
        _emit_ribbon_chunked(points, widths, colors, opacities, pen, filter_id, output)
    else:
        path_data = _build_ribbon_path(points, widths)
        if path_data:
            extra = f' filter="url(#{filter_id})"' if filter_id else ""
            output.write(
                f'\t\t\t<path d="{path_data}" '
                f'fill="{colors[0]}" opacity="{opacities[0]}"{extra}/>\n'
            )


# ====================================================================
# Per-point calculations
# ====================================================================


def _compute_point_widths(points, pen: Pen) -> list[float]:
    widths: list[float] = []
    last_w = 0.0
    for pt in points:
        w = pen.get_segment_width(pt.speed, pt.direction, pt.width, pt.pressure, last_w)
        w = max(w, 0.2)  # minimum to avoid degenerate paths
        widths.append(w)
        last_w = w
    return widths


def _smooth_widths(widths: list[float], passes: int = 1) -> list[float]:
    """Simple moving-average smoothing (window=3) to reduce jitter."""
    result = list(widths)
    n = len(result)
    if n < 3:
        return result
    for _ in range(passes):
        tmp = list(result)
        for i in range(1, n - 1):
            tmp[i] = (result[i - 1] + result[i] + result[i + 1]) / 3.0
        result = tmp
    return result


def _compute_point_styles(points, pen: Pen) -> tuple[list[str], list[float]]:
    colors: list[str] = []
    opacities: list[float] = []
    last_w = 0.0
    for pt in points:
        c = pen.get_segment_color(pt.speed, pt.direction, pt.width, pt.pressure, last_w)
        o = pen.get_segment_opacity(pt.speed, pt.direction, pt.width, pt.pressure, last_w)
        colors.append(c)
        opacities.append(o)
        last_w = pen.get_segment_width(pt.speed, pt.direction, pt.width, pt.pressure, last_w)
    return colors, opacities


# ====================================================================
# Ribbon path construction
# ====================================================================


def _compute_normals(points) -> list[tuple[float, float]]:
    """Compute unit normals perpendicular to the path direction at each point."""
    n = len(points)
    normals: list[tuple[float, float]] = []
    for i in range(n):
        if i == 0:
            dx = points[1].x - points[0].x
            dy = points[1].y - points[0].y
        elif i == n - 1:
            dx = points[-1].x - points[-2].x
            dy = points[-1].y - points[-2].y
        else:
            dx = points[i + 1].x - points[i - 1].x
            dy = points[i + 1].y - points[i - 1].y

        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-6:
            normals.append(normals[-1] if normals else (0.0, -1.0))
        else:
            # Perpendicular: rotate tangent 90 degrees
            normals.append((-dy / length, dx / length))
    return normals


def _build_ribbon_path(points, widths: list[float]) -> str:
    """Build an SVG path string for a filled variable-width ribbon.

    Constructs left and right offset curves from the centerline, then
    joins them into a closed polygon.
    """
    n = len(points)
    if n < 2:
        return ""

    normals = _compute_normals(points)

    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    for i in range(n):
        hw = widths[i] / 2.0
        nx, ny = normals[i]
        left.append((_xx(points[i].x + hw * nx), _yy(points[i].y + hw * ny)))
        right.append((_xx(points[i].x - hw * nx), _yy(points[i].y - hw * ny)))

    # Forward along left edge, backward along right edge, close
    parts = [f"M{left[0][0]:.2f},{left[0][1]:.2f}"]
    for i in range(1, n):
        parts.append(f"L{left[i][0]:.2f},{left[i][1]:.2f}")
    parts.append(f"L{right[-1][0]:.2f},{right[-1][1]:.2f}")
    for i in range(n - 2, -1, -1):
        parts.append(f"L{right[i][0]:.2f},{right[i][1]:.2f}")
    parts.append("Z")

    return " ".join(parts)


def _emit_ribbon_chunked(
    points,
    widths: list[float],
    colors: list[str],
    opacities: list[float],
    pen: Pen,
    filter_id: tp.Optional[str],
    output: io.StringIO,
) -> None:
    """Emit ribbon as small overlapping chunks for per-point style variation."""
    chunk_size = 4
    n = len(points)
    extra = f' filter="url(#{filter_id})"' if filter_id else ""
    i = 0
    while i < n - 1:
        end = min(i + chunk_size, n)
        chunk_pts = points[i:end]
        chunk_ws = widths[i:end]
        mid = min(i + len(chunk_pts) // 2, n - 1)
        if len(chunk_pts) >= 2:
            path_data = _build_ribbon_path(chunk_pts, chunk_ws)
            if path_data:
                output.write(
                    f'\t\t\t<path d="{path_data}" '
                    f'fill="{colors[mid]}" opacity="{opacities[mid]}"{extra}/>\n'
                )
        i = end - 1  # overlap by 1 point for continuity


# ====================================================================
# Text rendering (same as rmc)
# ====================================================================


def _draw_text(text: si.Text, output: io.StringIO) -> None:
    output.write('\t\t<g class="root-text" style="display:inline">')
    output.write(
        """
            <style>
                text.heading { font: 14pt serif; }
                text.bold { font: 8pt sans-serif bold; }
                text, text.plain { font: 7pt sans-serif; }
            </style>
"""
    )
    y_offset = _TEXT_TOP_Y
    doc = TextDocument.from_scene_item(text)
    for p in doc.contents:
        y_offset += _LINE_HEIGHTS.get(p.style.value, 70)
        xpos = text.pos_x
        ypos = text.pos_y + y_offset
        cls = p.style.value.name.lower()
        if str(p):
            output.write(
                f'\t\t\t<text x="{_xx(xpos)}" y="{_yy(ypos)}" '
                f'class="{cls}">{str(p).strip()}</text>\n'
            )
    output.write("\t\t</g>\n")
