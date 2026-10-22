from pathlib import Path

import pytest

from hwkit import labels

FONTS = Path("/System/Library/Fonts/Supplemental")
BLACK = FONTS / "Arial Black.ttf"
BOLD = FONTS / "Arial Bold.ttf"
RULES = labels.InlayRules(nozzle_d=0.6)
BOUNDS = (-50, 50, -50, 50)
pytestmark = pytest.mark.skipif(not BLACK.exists(), reason="macOS fonts not available")


def test_thin_text_is_rejected():
    solid = labels.text("IN", 3.5, 0, 0, 10.0, RULES, str(BOLD))
    with pytest.raises(ValueError, match="strokes"):
        labels.check_label("IN", solid, RULES, BOUNDS)


def test_printable_text_passes():
    result = labels.check_label("IN", labels.text("IN", 7.0, 0, 0, 10.0, RULES, str(BLACK)), RULES, BOUNDS)
    assert result["stroke_depth"] <= RULES.lost_depth_factor * RULES.min_feature


def test_glyphs_are_min_gap_apart():
    solid = labels.text("IN", 7.0, 0, 0, 10.0, RULES, str(BLACK))
    boxes = sorted((s.BoundingBox().xmin, s.BoundingBox().xmax) for s in solid.solids().vals())
    assert boxes[1][0] - boxes[0][1] >= RULES.min_gap - 1e-6


def test_polarity_symbol_passes():
    labels.check_label("polarity", labels.polarity_symbol(0, 0, 10.0, RULES), RULES, BOUNDS)


def test_label_outside_bounds_is_rejected():
    with pytest.raises(ValueError, match="outside"):
        labels.check_label("IN", labels.text("IN", 7.0, 0, 0, 10.0, RULES, str(BLACK)), RULES, (-1, 1, -1, 1))
