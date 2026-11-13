import math

from apps.routing.services.geo import EARTH_RADIUS_MILES, simplify_polyline

MILES_PER_DEGREE = EARTH_RADIUS_MILES * math.pi / 180


def test_simplify_drops_collinear_vertices_and_keeps_endpoints() -> None:
    line = [(i / 100, 0.0) for i in range(101)]

    assert simplify_polyline(line, 0.01) == [(0.0, 0.0), (1.0, 0.0)]


def test_simplify_keeps_a_corner_larger_than_the_tolerance() -> None:
    corner = [(0.0, 0.0), (0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (1.0, 1.0)]

    assert simplify_polyline(corner, 0.01) == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]


def test_simplify_drops_wiggles_smaller_than_the_tolerance() -> None:
    wiggle = 0.005 / MILES_PER_DEGREE  # 0.005 miles off the line
    line = [(0.0, 0.0), (0.5, wiggle), (1.0, 0.0)]

    assert simplify_polyline(line, 0.01) == [(0.0, 0.0), (1.0, 0.0)]


def test_simplify_short_lines_unchanged() -> None:
    assert simplify_polyline([(0.0, 0.0), (1.0, 1.0)], 0.01) == [(0.0, 0.0), (1.0, 1.0)]


def test_simplify_closed_loop_keeps_shape() -> None:
    loop = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]

    assert simplify_polyline(loop, 0.01) == loop
