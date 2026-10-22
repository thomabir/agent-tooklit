"""Example: plate with an inlaid label -> Bambu project -> slice verification.

Run in the toolkit folder:
  uv run hwkit bambu flatten --out build/example/profiles
  uv run hwkit bambu template --profiles build/example/profiles --out build/example/bambu-project-settings.json --work build/example/template
  uv run python examples/inlay_lid.py
  uv run hwkit bambu verify build/example/out/lid.3mf --labels build/example/out/labels.stl --body build/example/out/lid.stl --out build/example/verify
"""

import json
from pathlib import Path

import cadquery as cq

from hwkit import lab, labels
from hwkit.bambu import INLAY_OBJECT_SETTINGS
from hwkit.bambu.project import label_first_plate_settings, write_project
from hwkit.outputs import OutputGuard

BUILD = Path(__file__).parent.parent / "build" / "example"
LAB = lab.load()
RULES = labels.InlayRules(nozzle_d=LAB["printer"]["nozzle_d"])
TOP = 3.0  # mm, plate thickness; the label face is at z = TOP in the assembled orientation

plate = cq.Workplane().box(40, 30, TOP).translate((0, 0, TOP / 2))
label = labels.text("OUT", 7.0, 0, 0, TOP, RULES, LAB["tools"]["label_font"])
labels.check_label("OUT", label, RULES, (-18, 18, -13, 13))  # ValueError if not printable
plate = plate.cut(label)


def flip(shape):
    """Print orientation: label face on the build plate."""
    return shape.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, TOP))


template = json.loads((BUILD / "bambu-project-settings.json").read_text())


def project(path):
    obj = {"name": "lid", "parts": [("lid", flip(plate).val(), 1), ("labels", flip(label).val(), 2)], "settings": INLAY_OBJECT_SETTINGS, "center": tuple(LAB["printer"]["plate_center"])}
    write_project(path, [obj], label_first_plate_settings(RULES.depth, template, 2, 1), template)


def stl(shape):
    return lambda path: cq.exporters.export(flip(shape), str(path), tolerance=0.01, angularTolerance=0.1)


OutputGuard(BUILD / "out").write_all({"lid.3mf": project, "lid.stl": stl(plate), "labels.stl": stl(label)})
print(f"written: {BUILD / 'out'}")
