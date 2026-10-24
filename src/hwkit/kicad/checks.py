"""Checks of a KiCad project: title blocks, board outline, zone fill, BOM fields.

Each check returns (lines, issues). Lines starting with "NOTE:" are recommendations, not issues.
"""

import math
import re

from . import sexp

TITLE_KEYS = ("title", "rev", "date", "company")
VERSION_RE = re.compile(r"^\d+\.\d+$")  # Major.Minor
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def title_block(root):
    tb = sexp.child(root, "title_block")
    return {k: (sexp.value(tb, k, "") if tb is not None else "") for k in TITLE_KEYS}


def check_title_blocks(blocks, id_pattern=None):
    """blocks: {file name: title block dict}. Fields filled, version Major.Minor, ISO date, title starts with the project identifier (regular expression id_pattern), all files equal."""
    lines, issues = [], []
    first = next(iter(blocks.values()))
    lines.append(f"title block ({len(blocks)} files): " + ", ".join(f"{k}={first[k]!r}" for k in TITLE_KEYS))
    for name, tb in blocks.items():
        if id_pattern and tb["title"] and not re.match(id_pattern, tb["title"]):
            issues.append(f"{name}: title {tb['title']!r} does not start with a project identifier ({id_pattern})")
        for k in TITLE_KEYS:
            if not tb[k]:
                issues.append(f"{name}: title block field '{k}' is empty")
        if tb["rev"] and not VERSION_RE.match(tb["rev"]):
            issues.append(f"{name}: rev {tb['rev']!r} is not Major.Minor")
        if tb["date"] and not DATE_RE.match(tb["date"]):
            issues.append(f"{name}: date {tb['date']!r} is not YYYY-MM-DD")
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
    """Board outline from Edge.Cuts: sample points for the bounding box."""

    def __init__(self, root):
        self.points = []
        for n in root[1:]:
            if not isinstance(n, list) or sexp.value(n, "layer") != "Edge.Cuts":
                continue
            kind = n[0]
            if kind in ("gr_line", "gr_rect"):
                self.points += [sexp.xy(n, "start"), sexp.xy(n, "end")]
            elif kind == "gr_arc":
                self.points += _arc_points(sexp.xy(n, "start"), sexp.xy(n, "mid"), sexp.xy(n, "end"))
            elif kind == "gr_circle":
                c, e = sexp.xy(n, "center"), sexp.xy(n, "end")
                r = math.dist(c, e)
                self.points += [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
            elif kind == "gr_poly":
                for q in sexp.child(n, "pts")[1:]:
                    if q[0] == "xy":
                        self.points.append((float(q[1]), float(q[2])))
                    elif q[0] == "arc":
                        self.points += _arc_points(sexp.xy(q, "start"), sexp.xy(q, "mid"), sexp.xy(q, "end"))

    def bbox(self):
        xs, ys = [p[0] for p in self.points], [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)


def _net_names(root):
    return {n[1]: n[2] for n in sexp.children(root, "net") if len(n) > 2}


def _net(node, names):
    n = sexp.child(node, "net")
    if n is None or len(n) < 2:
        return sexp.value(node, "net_name")
    return names.get(n[1], n[1])


def check_board(root):
    """Outline present, all copper zones filled (an unfilled zone gives Gerbers without the zone copper)."""
    lines, issues = [], []

    outline = Outline(root)
    if not outline.points:
        return lines, ["no Edge.Cuts outline"]
    x0, y0, x1, y1 = outline.bbox()
    lines.append(f"outline: {x1 - x0:.3f} mm × {y1 - y0:.3f} mm, origin ({x0:.3f}, {y0:.3f}) mm")

    names = _net_names(root)
    for z in sexp.children(root, "zone"):
        if sexp.child(z, "keepout") is not None:
            continue
        if not sexp.children(z, "filled_polygon"):
            layers = sexp.child(z, "layers") or sexp.child(z, "layer")
            issues.append(f"zone {_net(z, names) or '(no net)'} on {', '.join(layers[1:])} is not filled; fill the zones (key B) and save")
    return lines, issues


OPTIONAL_ROLES = {"order_qty", "notes", "lcsc"}


def check_bom(rows, fields):
    """rows: BOM rows (dict, keys = field labels). fields: {role: field name}. All roles must have a value, except OPTIONAL_ROLES."""
    lines, issues = [f"BOM: {len(rows)} line(s), {sum(int(r['Qty']) for r in rows)} part(s)"], []
    domains = {"digikey": "digikey.", "mouser": "mouser."}
    for r in rows:
        refs = r["Refs"]
        for role, name in fields.items():
            v = r.get(name, "").strip()
            if v in ("", "~"):
                if role not in OPTIONAL_ROLES:
                    issues.append(f"{refs}: field '{name}' is empty")
            elif role == "datasheet" and not v.startswith(("https://", "http://")):
                issues.append(f"{refs}: field '{name}' is not a link: {v!r}")
            elif role == "order_qty" and not v.isdigit():
                issues.append(f"{refs}: field '{name}' is not a non-negative integer: {v!r}")
            elif role == "digikey_pn" and not v.endswith("-ND"):
                issues.append(f"{refs}: field '{name}' is not a DigiKey part number (ends with -ND): {v!r}")
            elif role in domains and not (v.startswith("https://") and domains[role] in v):
                issues.append(f"{refs}: field '{name}' is not a {domains[role]} https link: {v!r}")
    return lines, issues
