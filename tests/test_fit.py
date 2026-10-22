import cadquery as cq
import pytest

from hwkit.fit import report


def wall_with_window(window_top):
    """Wall in the xz plane with a window from z = 0 to window_top."""
    wall = cq.Workplane("XY").box(10, 2, 5, centered=False).translate((0, 0, -2))
    window = cq.Workplane("XY").box(4, 4, window_top, centered=False).translate((3, -1, 0))
    return wall.cut(window).val()


def hook(top):
    """Hook block in the window from z = 0.2 to top."""
    return cq.Workplane("XY").box(2, 1, top - 0.2, centered=False).translate((4, 0.5, 0.2)).val()


@pytest.mark.parametrize(("hook_top", "expect_bad"), [(0.9, True), (0.3, False)])
def test_latch_margin(hook_top, expect_bad):
    h = hook(hook_top)
    lid = h.fuse(cq.Workplane("XY").box(10, 2, 1, centered=False).translate((0, 0, 40)).val())
    bad = report(wall_with_window(1.0), lid, {}, flexing=h, latches=h, latch_margin=0.6)
    assert any("latches" in b for b in bad) == expect_bad


def test_latch_margin_negative():
    h = hook(0.9)
    with pytest.raises(ValueError):
        report(wall_with_window(1.0), h, {}, latches=h, latch_margin=-0.1)
