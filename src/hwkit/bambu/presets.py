"""Flat Bambu presets for the command line, and the project settings template.

- The command line does not resolve the "inherits" chain of a preset: flatten() merges it.
- Start G-code and other long values are in "<preset> template <key>.json" files outside the "inherits" chain: load_preset() applies them.
- A project 3MF needs Metadata/project_settings.config with one list entry per filament for all per-filament keys and an n × n flush matrix, else the command line stops (segmentation fault, "Failed slicing").
- The GUI applies only the project keys listed in different_settings_to_system over the system preset: make_template() lists each key of lab.process.choices.
- Preset arguments on the command line replace the project settings: verify in project mode (slice_file() without profiles_dir).
"""

import glob
import json
import zipfile
from pathlib import Path

from .slicer import slice_file

TEMPLATE_META_KEYS = ("name", "type", "from", "setting_id", "instantiation", "inherits")
PER_FILAMENT_EXTRA_KEYS = ("default_filament_colour", "pre_start_fan_time")  # per-filament lists that are not in the filament presets


def load_preset(lab, kind, name):
    """Preset merged with its "inherits" parents, plus the "<name> template <key>.json" files of each preset in the chain (child wins)."""
    root = Path(lab["tools"]["bambu_profiles"]) / kind
    data = json.loads((root / f"{name}.json").read_text())
    if "inherits" in data:
        merged = load_preset(lab, kind, data["inherits"])
        merged.update(data)
        data = merged
    for template in sorted(root.glob(f"{glob.escape(name)} template *.json")):
        data.update({k: v for k, v in json.loads(template.read_text()).items() if k not in TEMPLATE_META_KEYS})
    return data


def flatten(lab, out_dir):
    """Write machine.json, process.json, filament1.json, ... into out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    presets = [("machine", lab["printer"]["bambu_machine"], "machine.json"), ("process", lab["process"]["bambu_process"], "process.json")]
    presets += [("filament", f["bambu"], f"filament{i}.json") for i, f in enumerate(lab["filaments"], start=1)]
    for kind, name, filename in presets:
        data = load_preset(lab, kind, name)
        data.pop("inherits", None)
        data["from"] = "system"
        (out_dir / filename).write_text(json.dumps(data, indent=1) + "\n")
    return out_dir


def _cube_stl(path, size=10.0):
    v = [(x, y, z) for x in (0, size) for y in (0, size) for z in (0, size)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    lines = ["solid cube"]
    for a, b, c, d in quads:
        for tri in ((a, b, c), (a, c, d)):
            lines += ["facet normal 0 0 0", " outer loop"] + [f"  vertex {v[i][0]} {v[i][1]} {v[i][2]}" for i in tri] + [" endloop", "endfacet"]
    path.write_text("\n".join(lines + ["endsolid cube"]) + "\n")


def make_template(lab, profiles_dir, work_dir):
    """Project settings dict for hwkit.bambu.project.write_project().

    1. Slice a cube with the flat presets; take Metadata/project_settings.config from sliced.3mf.
    2. Make every per-filament list one entry per filament (the export has single entries).
    3. Flush matrix n x n, vector 2 n.
    4. Apply lab["process"]["choices"]; enter preset keys in different_settings_to_system, else the GUI uses the system value.
    5. Check that all *_gcode keys equal machine.json.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    cube = work_dir / "cube.stl"
    _cube_stl(cube)
    result = slice_file(cube, work_dir / "slice", lab, profiles_dir=profiles_dir)
    if result["return_code"] != 0:
        raise RuntimeError(f"template slice failed: {result}")
    settings = json.loads(zipfile.ZipFile(work_dir / "slice" / "sliced.3mf").read("Metadata/project_settings.config"))
    profiles_dir = Path(profiles_dir)
    n = len(lab["filaments"])

    filament_keys = set(json.loads((profiles_dir / "filament1.json").read_text())) | set(PER_FILAMENT_EXTRA_KEYS)
    for key, value in settings.items():
        if (key.startswith("filament") or key in filament_keys) and isinstance(value, list) and len(value) == 1 and n > 1:
            settings[key] = value * n
    settings["filament_colour"] = [f["colour"] for f in lab["filaments"]]
    vol = lab["flush"]["volumes"]
    settings["flush_volumes_matrix"] = [str(vol[i][j]) for i in range(n) for j in range(n)]
    settings["flush_volumes_vector"] = [lab["flush"]["vector_entry"]] * (2 * n)

    choices = lab["process"].get("choices", {})
    settings.update(choices)
    different = settings["different_settings_to_system"]  # [process, filament 1..n, printer]; ";"-separated keys
    for index, preset in ((0, "process.json"), (len(different) - 1, "machine.json")):
        keys = set(json.loads((profiles_dir / preset).read_text())) & set(choices)
        listed = [k for k in different[index].split(";") if k]
        different[index] = ";".join(sorted(set(listed) | keys))

    machine = json.loads((profiles_dir / "machine.json").read_text())
    wrong = [k for k in machine if k.endswith("_gcode") and settings.get(k) != machine[k]]
    if wrong:
        raise RuntimeError(f"G-code keys differ from machine.json: {wrong}")
    return settings
