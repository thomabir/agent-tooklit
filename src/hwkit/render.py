"""Exploded-view renders with Blender in background mode."""

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent / "blender" / "exploded.py"
DEFAULT_VIEWS = {"front": [-1.0, -1.6, 1.1], "rear": [1.2, 1.6, 1.0], "below": [0.9, -1.6, -0.9]}  # camera directions, case frame


def kicad_glb_matrix(pcb_w, pcb_t, z=0.0, origin=(100.0, -100.0)):
    """4x4 matrix: KiCad GLB (metres, STEP frame) -> case frame (mm) rotated 180° about z, PCB top at z. Same frame as hwkit.fit.kicad_rotated_frame()."""
    return [[-1000.0, 0, 0, pcb_w + origin[0]], [0, -1000.0, 0, origin[1]], [0, 0, 1000.0, -pcb_t + z], [0, 0, 0, 1]]


def exploded(lab, out_dir, name, parts, glb=None, views=None, resolution=(1400, 1100), samples=64):
    """Render. parts: [{"stl", "rgba", "z"}]. glb: {"path", "matrix"}. Returns the path of the side-by-side image."""
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = {"out_dir": str(out_dir), "name": name, "parts": parts, "glb": glb, "views": views or DEFAULT_VIEWS, "resolution": list(resolution), "samples": samples}
    cfg_path = out_dir / f"{name}.json"
    cfg_path.write_text(json.dumps(cfg, indent=1, default=str))
    r = subprocess.run([lab["tools"]["blender"], "-b", "--python", str(SCRIPT), "--", str(cfg_path)], check=False, capture_output=True, text=True)
    image = out_dir / f"{name}.png"
    if r.returncode != 0 or "Traceback" in r.stdout or not image.exists():
        raise RuntimeError(f"Blender failed:\n{r.stdout[-3000:]}\n{r.stderr[-2000:]}")
    return image
