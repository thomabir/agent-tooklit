"""Render a reference project with hwkit.render. Usage: uv run python tests/reference_render.py <reference project folder>"""

import sys
from pathlib import Path

from hwkit import lab, render

REF = Path(sys.argv[1]) / "case" / "assembly"
DARK, WHITE = [0.10, 0.11, 0.12, 1.0], [0.95, 0.95, 0.95, 1.0]
image = render.exploded(
    lab.load(),
    Path(__file__).parent.parent / "build" / "reference" / "render",
    "render-exploded",
    parts=[{"stl": str(REF / "assembly-base.stl"), "rgba": DARK, "z": 0}, {"stl": str(REF / "assembly-lid.stl"), "rgba": DARK, "z": 52}, {"stl": str(REF / "assembly-labels.stl"), "rgba": WHITE, "z": 52}],
    glb={"path": str(REF / "pcb-assembly.glb"), "matrix": render.kicad_glb_matrix(33.0, 1.6, z=22)},
)
print(image)
