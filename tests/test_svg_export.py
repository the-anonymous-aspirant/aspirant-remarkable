"""Unit tests for the variable-width ribbon SVG exporter."""

import math
from types import SimpleNamespace

from app.svg_export import (
    _compute_normals,
    _build_ribbon_path,
    _compute_point_widths,
    _smooth_widths,
)


def _make_point(x, y, speed=0, direction=0, width=8, pressure=128):
    """Create a mock point with the same attributes as rmscene points."""
    return SimpleNamespace(
        x=x, y=y, speed=speed, direction=direction, width=width, pressure=pressure,
    )


# ---- Normal computation ----


def test_normals_horizontal_line():
    """Horizontal line should produce vertical normals."""
    points = [_make_point(0, 0), _make_point(10, 0), _make_point(20, 0)]
    normals = _compute_normals(points)
    assert len(normals) == 3
    for nx, ny in normals:
        assert abs(nx - 0.0) < 1e-6
        assert abs(ny - (-1.0)) < 1e-6 or abs(ny - 1.0) < 1e-6


def test_normals_vertical_line():
    """Vertical line should produce horizontal normals."""
    points = [_make_point(0, 0), _make_point(0, 10), _make_point(0, 20)]
    normals = _compute_normals(points)
    for nx, ny in normals:
        assert abs(ny - 0.0) < 1e-6
        length = math.sqrt(nx * nx + ny * ny)
        assert abs(length - 1.0) < 1e-6


def test_normals_degenerate_points():
    """Coincident points should not crash — fallback normal is used."""
    points = [_make_point(5, 5), _make_point(5, 5), _make_point(5, 5)]
    normals = _compute_normals(points)
    assert len(normals) == 3
    # All normals should be valid (non-NaN, non-zero length)
    for nx, ny in normals:
        assert not math.isnan(nx) and not math.isnan(ny)


# ---- Ribbon path building ----


def test_ribbon_path_two_points():
    """Simplest ribbon: two points should produce a closed quadrilateral."""
    points = [_make_point(0, 0), _make_point(100, 0)]
    widths = [10.0, 10.0]
    path = _build_ribbon_path(points, widths)
    assert path.startswith("M")
    assert "Z" in path
    # Should have exactly 4 L commands (quad: 2 left + connect + 1 right + close)
    assert path.count("L") == 3  # left[1], right[1], right[0]


def test_ribbon_path_empty():
    """Fewer than 2 points should return empty string."""
    assert _build_ribbon_path([_make_point(0, 0)], [5.0]) == ""
    assert _build_ribbon_path([], []) == ""


def test_ribbon_path_varying_width():
    """Path with varying widths should produce a non-rectangular ribbon."""
    points = [_make_point(0, 0), _make_point(50, 0), _make_point(100, 0)]
    widths = [5.0, 20.0, 5.0]  # bulge in the middle
    path = _build_ribbon_path(points, widths)
    assert path.startswith("M")
    assert "Z" in path
    # The path should have coordinates — basic sanity
    assert path.count("L") == 5  # 2 left + connect + 2 right


def test_ribbon_path_contains_path_elements():
    """Ribbon SVG path should use M, L, Z commands."""
    points = [_make_point(i * 10, i * 5) for i in range(5)]
    widths = [4.0] * 5
    path = _build_ribbon_path(points, widths)
    assert "M" in path
    assert "L" in path
    assert "Z" in path


# ---- Width computation ----


def test_smooth_widths_preserves_endpoints():
    widths = [1.0, 5.0, 10.0, 5.0, 1.0]
    smoothed = _smooth_widths(widths)
    assert smoothed[0] == widths[0]
    assert smoothed[-1] == widths[-1]


def test_smooth_widths_reduces_spike():
    widths = [5.0, 5.0, 100.0, 5.0, 5.0]
    smoothed = _smooth_widths(widths)
    # The spike at index 2 should be reduced
    assert smoothed[2] < widths[2]


def test_smooth_widths_short_list():
    """Lists shorter than 3 should be returned unchanged."""
    assert _smooth_widths([5.0]) == [5.0]
    assert _smooth_widths([3.0, 7.0]) == [3.0, 7.0]
