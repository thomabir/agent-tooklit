"""Bambu Studio command-line slicing."""

import re
import subprocess
from pathlib import Path


def slice_file(input_path, out_dir, lab, profiles_dir=None, process_json=None):
    """Slice a 3MF or STL. Output: <out_dir>/plate_1.gcode, sliced.3mf, log.txt.

    profiles_dir None: project mode, the slicer uses only the settings in the project 3MF (as the GUI).
    profiles_dir given: flat presets from hwkit.bambu.presets.flatten(); they replace the project settings. process_json replaces the process preset.
    Returns {"exit_status", "return_code", "message", "log"}.
    """
    input_path = Path(input_path).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [lab["tools"]["bambu_studio"], "--debug", "3", "--slice", "0"]
    if profiles_dir is not None:
        p = Path(profiles_dir).resolve()
        process = Path(process_json).resolve() if process_json else p / "process.json"
        filaments = sorted(p.glob("filament*.json"))
        cmd += ["--load-settings", f"{p / 'machine.json'};{process}", "--load-filaments", ";".join(str(f) for f in filaments)]
    cmd += ["--outputdir", str(out_dir), "--export-3mf", "sliced.3mf", str(input_path)]  # --export-3mf is relative to --outputdir
    log = out_dir / "log.txt"
    with open(log, "w") as f:
        status = subprocess.run(cmd, cwd=out_dir, stdout=f, stderr=subprocess.STDOUT).returncode  # temporary files go into cwd
    text = log.read_text(errors="replace")
    m = re.findall(r"return_code=(-?\d+), error_message=([^,\n]*)", text)
    code, message = (int(m[-1][0]), m[-1][1]) if m else (None, "no return code in log")
    for marker in ("Segmentation", "Flush volumes matrix do not match"):
        if marker in text:
            message += f"; log contains '{marker}'"
    return {"exit_status": status, "return_code": code, "message": message, "log": log}
