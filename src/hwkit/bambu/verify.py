"""Full verification of a Bambu print project with inlaid labels: project check, project-mode slice, G-code settings, filament order, coverage.

The result is a "slice verified" state, not a print result. See skills/bambu-print-prep/SKILL.md.
"""

import json
import zipfile
from pathlib import Path

from . import checks, gcode
from .project import LABEL_LAYER_ACCELERATION, LABEL_LAYER_SPEED, label_layers
from .slicer import slice_file

MIN_LABEL_COVERAGE = 0.97  # fraction of label area covered by the label filament, layer 1
MAX_BODY_IN_LABELS = 0.02  # fraction of label area covered by the body filament, layer 1
MAX_GAPS = 3.0  # mm2, layer 1 gaps wider than the gap width
FEED_RATE_TOLERANCE = 0.5  # mm/s, G-code feed rates are rounded to mm/min


def verify(project, labels_stl, body_stl, out_dir, lab, label_filament=2, body_filament=1):
    """Print a report. Returns the list of issues (empty = all criteria met)."""
    out_dir = Path(out_dir)
    lines, issues = checks.check_project(project, plate_first_layer=f"{label_filament} {body_filament}")
    print("\n".join(lines))

    result = slice_file(project, out_dir, lab)  # project mode
    print(f"slice: return code {result['return_code']}, {result['message']}")
    if result["return_code"] != 0:
        return issues + [f"slice failed: {result['message']} (log {result['log']})"]
    g = out_dir / "plate_1.gcode"

    glines, gissues = checks.check_gcode_settings(g, project, extra_keys=lab["process"].get("choices", {}).keys())
    print("\n".join(glines))
    issues += gissues

    seq = gcode.filament_sequence(g)
    print(f"filament sequence (| = layer change): {' '.join(seq)}")
    if not seq or seq[0] != f"F{label_filament}":
        issues.append(f"layer 1 does not start with filament {label_filament}")

    res = gcode.coverage(g, labels_stl, body_stl, region=checks.inlay_region(project), png=out_dir / "coverage.png")
    for r in res:
        pf = "; ".join(f"filament {f}: inside labels {v['inside_labels']:.1f}, outside {v['outside_labels']:.1f}" for f, v in r["per_filament"].items())
        print(f"layer {r['layer']}: label area {r['label_area']:.1f} mm2, not covered {r['label_not_covered']:.2f}, top not covered {r['top_not_covered']:.2f}, gaps {r['gaps']:.2f} mm2 | {pf}")
    first = res[0]
    lab_cov = first["per_filament"].get(label_filament, {}).get("inside_labels", 0) / first["label_area"]
    body_in = first["per_filament"].get(body_filament, {}).get("inside_labels", 0) / first["label_area"]
    if lab_cov < MIN_LABEL_COVERAGE:
        issues.append(f"layer 1 label coverage {lab_cov:.1%} < {MIN_LABEL_COVERAGE:.0%}")
    if body_in > MAX_BODY_IN_LABELS:
        issues.append(f"layer 1 body filament in labels {body_in:.1%} > {MAX_BODY_IN_LABELS:.0%}")
    if first["gaps"] > MAX_GAPS:
        issues.append(f"layer 1 gaps {first['gaps']:.2f} mm2 > {MAX_GAPS} mm2")
    print(f"coverage plot: {out_dir / 'coverage.png'}")

    import trimesh

    project_settings = json.loads(zipfile.ZipFile(project).read("Metadata/project_settings.config"))
    n_layers = label_layers(round(float(trimesh.load(labels_stl).bounds[1][2]), 3), project_settings)
    rates, accelerations = gcode.max_feed_rates(g, n_layers)
    print(f"layers with labels (see project.slow_label_layers): largest extrusion feed rate {', '.join(f'{r:.0f}' for r in rates)} mm/s (limit {LABEL_LAYER_SPEED} mm/s), M201 limit {', '.join(f'{a:.0f}' for a in accelerations)} mm/s² (limit {LABEL_LAYER_ACCELERATION} mm/s²)")
    issues += [f"layer {k} feed rate {r:.0f} mm/s > {LABEL_LAYER_SPEED} mm/s" for k, r in enumerate(rates, start=1) if r > LABEL_LAYER_SPEED + FEED_RATE_TOLERANCE]
    issues += [f"layer {k} M201 limit {a:.0f} mm/s² > {LABEL_LAYER_ACCELERATION} mm/s²" for k, a in enumerate(accelerations, start=1) if a > LABEL_LAYER_ACCELERATION]
    return issues
