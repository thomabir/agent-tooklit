"""Inlaid multi-material labels on a flat face that prints on the build plate.

Rules: every stroke >= 2 nozzle diameters, every gap (counters, letter spacing) >= min_gap.
check_label() tests this with a morphological opening and the Hausdorff distance.
"""

import math
from dataclasses import dataclass

import cadquery as cq
from shapely.geometry import Polygon
from shapely.ops import unary_union


@dataclass(frozen=True)
class InlayRules:
    nozzle_d: float  # mm
    depth: float = 0.6  # mm, inlay depth
    gap_extra: float = 0.3  # mm, added to min_feature for gaps. Narrow islands of body material inside a glyph stay empty.
    lost_depth_factor: float = 1.5  # removed region may extend this multiple of the opening width. Passes corners down to approx. 30°.

    @property
    def min_feature(self):
        return 2 * self.nozzle_d

    @property
    def min_gap(self):
        return self.min_feature + self.gap_extra

    @property
    def symbol_stroke(self):
        return self.min_feature + 0.1


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _cylinder_z(x, y, d, z0, z1):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(d / 2).extrude(z1 - z0)


def text(txt, size, x, y, z_top, rules, font):
    """Text centered at (x, y), from z_top - depth to z_top. Glyph bounding boxes are at least rules.min_gap apart."""
    raw = cq.Workplane("XY").workplane(offset=z_top - rules.depth).text(txt, size, rules.depth, fontPath=font, halign="center", valign="center")
    glyphs = []  # solids with overlapping x ranges belong to one glyph
    for solid in sorted(raw.solids().vals(), key=lambda s: s.BoundingBox().xmin):
        bb = solid.BoundingBox()
        if glyphs and bb.xmin < glyphs[-1][1]:
            glyphs[-1][0].append(solid)
            glyphs[-1][1] = max(glyphs[-1][1], bb.xmax)
        else:
            glyphs.append([[solid], bb.xmax, bb.xmin])
    shift = 0.0
    placed = []
    prev_xmax = None
    for solids, xmax, xmin in glyphs:
        if prev_xmax is not None:
            shift += max(0.0, rules.min_gap - (xmin - prev_xmax))
        prev_xmax = xmax
        placed += [s.translate(cq.Vector(shift, 0, 0)) for s in solids]
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound(placed).translate(cq.Vector(x - shift / 2, y, 0))])


def polarity_symbol(x, y, z_top, rules):
    """Centre-positive DC symbol: minus, ring with gap, centre dot, plus."""
    z0 = z_top - rules.depth
    w = rules.symbol_stroke
    gap = rules.min_gap + 0.2
    dot_r = w
    r_in = dot_r + gap
    r_out = r_in + w
    arm = 1.25 * w  # half length of the plus and minus arms
    line = 2 * w
    ring = cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(r_out).circle(r_in).extrude(rules.depth)
    ring = ring.cut(_box(x, x + r_out + 1, y - w / 2 - gap, y + w / 2 + gap, z0 - 1, z_top + 1))
    dot = _cylinder_z(x, y, 2 * dot_r, z0, z_top)
    right_end = x + r_out + line
    left_end = x - r_out - line
    right_line = _box(x, right_end, y - w / 2, y + w / 2, z0, z_top)
    left_line = _box(left_end, x - r_in, y - w / 2, y + w / 2, z0, z_top)
    px = right_end + gap + arm
    plus = _box(px - arm, px + arm, y - w / 2, y + w / 2, z0, z_top).union(_box(px - w / 2, px + w / 2, y - arm, y + arm, z0, z_top))
    mx = left_end - gap - arm
    minus = _box(mx - arm, mx + arm, y - w / 2, y + w / 2, z0, z_top)
    return ring.union(dot).union(right_line).union(left_line).union(plus).union(minus)


def fit_inside(solid, bounds):
    """Move a label by the smallest distance that puts it inside bounds = (x0, x1, y0, y1)."""
    bb = solid.val().BoundingBox()
    x0, x1, y0, y1 = bounds
    dx = max(0.0, x0 - bb.xmin) - max(0.0, bb.xmax - x1)
    dy = max(0.0, y0 - bb.ymin) - max(0.0, bb.ymax - y1)
    return solid.translate((dx, dy, 0))


def top_outline(solid):
    """Outline of a label in its top plane, as a shapely geometry."""
    tris = []
    for f in solid.faces(">Z").vals():
        v, t = f.tessellate(0.01, 0.1)
        tris += [Polygon([(v[i].x, v[i].y) for i in tri]).buffer(1e-4) for tri in t]
    return unary_union(tris).buffer(-1e-4).buffer(0)


def lost_depth(geom, width):
    """Largest distance from a point of geom to geom after a morphological opening with this width. inf if nothing remains."""
    r = width / 2 * 0.98
    opened = geom.buffer(-r).buffer(r)
    return math.inf if opened.is_empty else geom.hausdorff_distance(opened)


def check_label(name, solid, rules, bounds):
    """Raise ValueError if a stroke < min_feature, a gap < min_gap, or the label is outside bounds = (x0, x1, y0, y1). Returns the measured values."""
    geom = top_outline(solid)
    stroke = lost_depth(geom, rules.min_feature)
    gaps = geom.buffer(2 * rules.min_gap).difference(geom)  # band around the label: counters and letter spacing
    gap = lost_depth(gaps, rules.min_gap)
    gx0, gy0, gx1, gy1 = geom.bounds
    x0, x1, y0, y1 = bounds
    result = {"name": name, "stroke_depth": stroke, "gap_depth": gap, "bounds": (gx0, gx1, gy0, gy1)}
    if stroke > rules.lost_depth_factor * rules.min_feature:
        raise ValueError(f"label {name}: strokes narrower than {rules.min_feature} mm")
    if gap > rules.lost_depth_factor * rules.min_gap:
        raise ValueError(f"label {name}: gaps narrower than {rules.min_gap} mm")
    if gx0 < x0 or gx1 > x1 or gy0 < y0 or gy1 > y1:
        raise ValueError(f"label {name}: outside {bounds}")
    return result
