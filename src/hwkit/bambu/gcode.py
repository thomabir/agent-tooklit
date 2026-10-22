"""Analysis of the first layers of a Bambu G-code file. See lessons.md (L13, L14)."""

import math
import re

from shapely.affinity import translate
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

EXCLUDED_FEATURES = ("tower", "skirt")
ARC_STEP = 0.05  # mm, chord length for G2/G3 interpolation


def _arc(x, y, nx, ny, i, j, ccw):
    cx, cy = x + i, y + j
    r = math.hypot(x - cx, y - cy)
    a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
    if ccw:
        while a1 <= a0:
            a1 += 2 * math.pi
    else:
        while a1 >= a0:
            a1 -= 2 * math.pi
    n = max(2, int(abs(a1 - a0) * r / ARC_STEP))
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def read_paths(gcode, n_layers):
    """Extrusions of the first n_layers: list of layers, each a list of (points, line width, filament number from 1, feature)."""
    layers = []
    x = y = 0.0
    width, feature, filament = 0.6, "", 1
    for line in open(gcode):
        if line.startswith("; CHANGE_LAYER"):
            if len(layers) == n_layers:
                break
            layers.append([])
            continue
        if line.startswith("; FEATURE:"):
            feature = line.split(":", 1)[1].strip()
            continue
        if line.startswith("; LINE_WIDTH:"):
            width = float(line.split(":", 1)[1])
            continue
        m = re.match(r"^M620 S(\d+)A", line)  # filament change; T1000/T1100 are toolhead commands
        if m and int(m.group(1)) < 255:
            filament = int(m.group(1)) + 1
            continue
        if not line.startswith(("G1", "G2", "G3")):
            continue
        p = dict(re.findall(r"([XYEIJ])(-?[\d.]+)", line.split(";")[0]))
        nx, ny = float(p.get("X", x)), float(p.get("Y", y))
        pts = _arc(x, y, nx, ny, float(p.get("I", 0)), float(p.get("J", 0)), line.startswith("G3")) if line.startswith(("G2", "G3")) else [(x, y), (nx, ny)]
        if layers and float(p.get("E", 0)) > 0 and ("X" in p or "Y" in p) and not any(f in feature.lower() for f in EXCLUDED_FEATURES):
            layers[-1].append((pts, width, filament, feature))
        x, y = nx, ny
    return layers


def filament_sequence(gcode, n_events=7):
    """First filament changes and layer changes, as a list of "F<n>" and "|"."""
    events = []
    for line in open(gcode):
        if line.startswith("; CHANGE_LAYER"):
            events.append("|")
        else:
            m = re.match(r"^M620 S(\d+)A", line)
            if m and int(m.group(1)) < 255:
                events.append(f"F{int(m.group(1)) + 1}")
        if len(events) >= n_events:
            break
    return events


def footprint(paths):
    return unary_union([LineString(pts).buffer(w / 2) for pts, w, _, _ in paths if len(pts) > 1])


def mesh_section(mesh, z):
    """Section of a trimesh at height z as a shapely geometry (nested contours alternate material/hole)."""
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    geom = Polygon()
    for poly in sorted((Polygon(e[:, :2]) for e in sec.discrete), key=lambda q: -q.area):
        geom = geom.symmetric_difference(poly)
    return geom


def coverage(gcode, labels_stl, body_stl, region=None, layers=2, first_layer_height=0.3, layer_height=0.3, edge_exclusion=0.5, gap_width=0.2, png=None):
    """Per layer: label area per filament, uncovered top area, gaps wider than gap_width. Meshes in print orientation, aligned by the layer-1 bounding-box center in region."""
    import trimesh

    labels_mesh, body_mesh = trimesh.load(labels_stl), trimesh.load(body_stl)
    all_layers = read_paths(gcode, layers)
    if region:
        x0, x1, y0, y1 = region
        all_layers = [[p for p in L if all(x0 <= px <= x1 and y0 <= py <= y1 for px, py in p[0])] for L in all_layers]
    results, offset, z = [], None, 0.0
    plots = []
    for k, paths in enumerate(all_layers):
        h = first_layer_height if k == 0 else layer_height
        z_mid = z + h / 2
        z += h
        labels = mesh_section(labels_mesh, z_mid)
        top = labels.union(mesh_section(body_mesh, z_mid))
        covered = footprint(paths)
        if offset is None:
            cb, tb = covered.bounds, top.bounds
            offset = ((cb[0] + cb[2] - tb[0] - tb[2]) / 2, (cb[1] + cb[3] - tb[1] - tb[3]) / 2)
        labels, top = translate(labels, *offset), translate(top, *offset)
        per_filament = {}
        for f in sorted({p[2] for p in paths}):
            g = footprint([p for p in paths if p[2] == f])
            per_filament[f] = {"inside_labels": g.intersection(labels).area, "outside_labels": g.difference(labels).area}
        missing = top.buffer(-edge_exclusion).difference(covered)
        results.append({
            "layer": k + 1,
            "label_area": labels.area,
            "label_not_covered": labels.difference(covered).area,
            "top_not_covered": missing.area,
            "gaps": missing.buffer(-gap_width / 2).area,
            "per_filament": per_filament,
        })
        plots.append((covered, missing, labels))
    if png:
        _plot(plots, png)
    return results


def _plot(plots, png):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def fill(ax, geom, color):
        for p in getattr(geom, "geoms", [geom]):
            if p.is_empty or not hasattr(p, "exterior"):
                continue
            ax.fill(*p.exterior.xy, color=color, lw=0)
            for hole in p.interiors:
                ax.fill(*hole.xy, color="white", lw=0)

    fig, axes = plt.subplots(1, len(plots), figsize=(9 * len(plots), 12), squeeze=False)
    for k, (covered, missing, labels) in enumerate(plots):
        ax = axes[0][k]
        fill(ax, covered, "0.8")
        fill(ax, missing, "red")
        for p in getattr(labels, "geoms", [labels]):
            ax.plot(*p.exterior.xy, color="black", lw=0.5)
            for hole in p.interiors:
                ax.plot(*hole.xy, color="black", lw=0.5)
        ax.set_aspect("equal")
        ax.set_title(f"Layer {k + 1}: grey = extruded, red = not covered, black = label outline")
    fig.tight_layout()
    fig.savefig(png, dpi=100)
