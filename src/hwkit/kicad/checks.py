"""Checks of a KiCad project: title blocks, board outline, mounting holes, ground pour, BOM fields.

Each check returns (lines, issues). Lines starting with "NOTE:" are recommendations, not issues.
"""

import math
import re

from . import sexp

TITLE_KEYS = ("title", "rev", "date", "company")
VERSION_RE = re.compile(r"^\d+\.\d+$")  # Major.Minor
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SILK_VARIABLES = {"title": "${TITLE}", "rev": "${REVISION}", "date": "${ISSUE_DATE}", "company": "${COMPANY}"}


def title_block(root):
    tb = sexp.child(root, "title_block")
    return {k: (sexp.value(tb, k, "") if tb is not None else "") for k in TITLE_KEYS}


def check_title_blocks(blocks, author=None):
    """blocks: {file name: title block dict}. Fields filled, version Major.Minor, ISO date, author in company, all files equal."""
    lines, issues = [], []
    for name, tb in blocks.items():
        lines.append(f"{name}: " + ", ".join(f"{k}={tb[k]!r}" for k in TITLE_KEYS))
        for k in TITLE_KEYS:
            if not tb[k]:
                issues.append(f"{name}: title block field '{k}' is empty")
        if tb["rev"] and not VERSION_RE.match(tb["rev"]):
            issues.append(f"{name}: rev {tb['rev']!r} is not Major.Minor")
        if tb["date"] and not DATE_RE.match(tb["date"]):
            issues.append(f"{name}: date {tb['date']!r} is not YYYY-MM-DD")
        if author and tb["company"] and tb["company"] != author:
            issues.append(f"{name}: company {tb['company']!r} is not the author {author!r}")
    for k in TITLE_KEYS:
        values = {tb[k] for tb in blocks.values()}
        if len(values) > 1:
            issues.append(f"title block field '{k}' differs between files: {sorted(values)}")
    return lines, issues


def _arc_center(p0, p1, p2):
    (ax, ay), (bx, by), (cx, cy) = p0, p1, p2
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    return ((a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d, (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d)


def _unit(dx, dy):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 0 else (0.0, 0.0)


def _arc_end_direction(end, mid, center):
    """Tangent at an arc end point, pointing into the arc."""
    rx, ry = end[0] - center[0], end[1] - center[1]
    t = _unit(-ry, rx)
    if t[0] * (mid[0] - end[0]) + t[1] * (mid[1] - end[1]) < 0:
        t = (-t[0], -t[1])
    return t


def _arc_points(start, mid, end, n=64):
    c = _arc_center(start, mid, end)
    if c is None:
        return [start, end]
    r = math.dist(c, start)
    a0, am, a1 = (math.atan2(p[1] - c[1], p[0] - c[0]) for p in (start, mid, end))
    sweep = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sweep:
        sweep -= 2 * math.pi
    return [(c[0] + r * math.cos(a0 + sweep * i / n), c[1] + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


class Outline:
    """Board outline from Edge.Cuts: pieces with end points and tangents, and sample points for the bounding box."""

    def __init__(self, root):
        self.ends = []  # (point, outgoing direction)
        self.points = []
        self.sharp_rects = 0
        self.circles = 0
        for n in root[1:]:
            if not isinstance(n, list) or sexp.value(n, "layer") != "Edge.Cuts":
                continue
            kind = n[0]
            if kind == "gr_line":
                self._line(sexp.xy(n, "start"), sexp.xy(n, "end"))
            elif kind == "gr_arc":
                self._arc(sexp.xy(n, "start"), sexp.xy(n, "mid"), sexp.xy(n, "end"))
            elif kind == "gr_rect":
                (x0, y0), (x1, y1) = sexp.xy(n, "start"), sexp.xy(n, "end")
                self.points += [(x0, y0), (x1, y1)]
                if float(sexp.value(n, "radius", sexp.value(n, "corner_radius", 0))) <= 0:
                    self.sharp_rects += 1
            elif kind == "gr_circle":
                c, e = sexp.xy(n, "center"), sexp.xy(n, "end")
                r = math.dist(c, e)
                self.points += [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
                self.circles += 1
            elif kind == "gr_poly":
                self._poly(sexp.child(n, "pts"))

    def _line(self, a, b):
        self.ends += [(a, _unit(b[0] - a[0], b[1] - a[1])), (b, _unit(a[0] - b[0], a[1] - b[1]))]
        self.points += [a, b]

    def _arc(self, a, m, b):
        c = _arc_center(a, m, b)
        if c is None:
            self._line(a, b)
            return
        self.ends += [(a, _arc_end_direction(a, m, c)), (b, _arc_end_direction(b, m, c))]
        self.points += _arc_points(a, m, b)

    def _poly(self, pts):
        cursor = first = None
        for p in pts[1:]:
            if p[0] == "xy":
                q = (float(p[1]), float(p[2]))
                first = first or q
                if cursor is not None:
                    self._line(cursor, q)
                cursor = q
            elif p[0] == "arc":
                a, m, b = sexp.xy(p, "start"), sexp.xy(p, "mid"), sexp.xy(p, "end")
                first = first or a
                if cursor is not None and math.dist(cursor, a) > 1e-6:
                    self._line(cursor, a)
                self._arc(a, m, b)
                cursor = b
        if cursor is not None and first is not None and math.dist(cursor, first) > 1e-6:
            self._line(cursor, first)

    def bbox(self):
        xs, ys = [p[0] for p in self.points], [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def sharp_corners(self, max_turn_deg):
        """Junctions where the outline turns by more than max_turn_deg."""
        joints = {}
        for p, d in self.ends:
            joints.setdefault((round(p[0], 3), round(p[1], 3)), []).append(d)
        sharp = []
        for p, ds in joints.items():
            if len(ds) != 2:
                continue
            (ax, ay), (bx, by) = ds
            turn = 180 - math.degrees(math.acos(max(-1.0, min(1.0, ax * bx + ay * by))))
            if turn > max_turn_deg:
                sharp.append((p, turn))
        return sharp


def _reference(fp):
    for p in sexp.children(fp, "property"):
        if p[1] == "Reference":
            return p[2]
    for t in sexp.children(fp, "fp_text"):
        if t[1] == "reference":
            return t[2]
    return "?"


def _net_names(root):
    return {n[1]: n[2] for n in sexp.children(root, "net") if len(n) > 2}


def _net(node, names):
    n = sexp.child(node, "net")
    if n is None or len(n) < 2:
        return sexp.value(node, "net_name")
    return names.get(n[1], n[1])


def check_board(root, gnd_nets, hole_grid, corner_max_turn_deg, title=None):
    """Outline with rounded corners, mounting holes on the grid, filled ground pour, title text on the silkscreen."""
    lines, issues = [], []

    outline = Outline(root)
    if not outline.points:
        return lines, ["no Edge.Cuts outline"]
    x0, y0, x1, y1 = outline.bbox()
    lines.append(f"outline: {x1 - x0:.3f} mm × {y1 - y0:.3f} mm, origin ({x0:.3f}, {y0:.3f}) mm")
    if outline.sharp_rects:
        issues.append(f"{outline.sharp_rects} Edge.Cuts rectangle(s) without corner radius")
    for p, turn in outline.sharp_corners(corner_max_turn_deg):
        issues.append(f"sharp board corner at ({p[0]:.3f}, {p[1]:.3f}) mm, turn {turn:.0f}°")

    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    holes = [fp for fp in sexp.children(root, "footprint") if "mountinghole" in fp[1].lower()]
    if not holes:
        issues.append("no mounting holes (footprint library id with 'MountingHole')")
    for fp in holes:
        x, y = sexp.xy(fp, "at")
        dx, dy = x - x0, y - y0
        near = min(math.dist((x, y), c) for c in corners)
        lines.append(f"mounting hole {_reference(fp)}: ({dx:.3f}, {dy:.3f}) mm from outline origin, {near:.1f} mm from the nearest corner")
        for v, axis in ((dx, "x"), (dy, "y")):
            if abs(v / hole_grid - round(v / hole_grid)) * hole_grid > 1e-3:
                issues.append(f"mounting hole {_reference(fp)}: {axis} = {v:.3f} mm from outline origin is not on the {hole_grid} mm grid")

    names = _net_names(root)
    gnd_zones = [z for z in sexp.children(root, "zone") if _net(z, names) in gnd_nets]
    if not gnd_zones:
        issues.append(f"no zone on a ground net {list(gnd_nets)}")
    for z in gnd_zones:
        layers = sexp.child(z, "layers") or sexp.child(z, "layer")
        lines.append(f"ground zone {_net(z, names)} on {', '.join(layers[1:])}")
        if not sexp.children(z, "filled_polygon"):
            issues.append(f"ground zone {_net(z, names)} on {', '.join(layers[1:])} is not filled")
    gnd_tracks = sum(1 for s in sexp.children(root, "segment") if _net(s, names) in gnd_nets)
    if gnd_tracks:
        lines.append(f"NOTE: {gnd_tracks} track segment(s) on ground nets; the ground pour usually makes these connections")

    silk = " ".join(t[1] for t in root[1:] if isinstance(t, list) and t[:1] == ["gr_text"] and str(sexp.value(t, "layer", "")).endswith(".SilkS"))
    missing = [k for k, var in SILK_VARIABLES.items() if var not in silk and not (title and title.get(k) and title[k] in silk)]
    if missing:
        lines.append(f"NOTE: silkscreen text without title block field(s) {missing}; use {[SILK_VARIABLES[k] for k in missing]}")
    return lines, issues


def check_bom(rows, fields):
    """rows: BOM rows (dict, keys = field labels). fields: {role: field name} with roles manufacturer, mpn, digikey, mouser, and the optional role order_qty."""
    lines, issues = [f"BOM: {len(rows)} line(s), {sum(int(r['Qty']) for r in rows)} part(s)"], []
    domains = {"digikey": "digikey.", "mouser": "mouser."}
    optional = {"order_qty"}
    for r in rows:
        refs = r["Refs"]
        for role, name in fields.items():
            v = r.get(name, "").strip()
            if not v:
                if role not in optional:
                    issues.append(f"{refs}: field '{name}' is empty")
            elif role == "order_qty" and not v.isdigit():
                issues.append(f"{refs}: field '{name}' is not a non-negative integer: {v!r}")
            elif role in domains and not (v.startswith("https://") and domains[role] in v):
                issues.append(f"{refs}: field '{name}' is not a {domains[role]} https link: {v!r}")
    return lines, issues
