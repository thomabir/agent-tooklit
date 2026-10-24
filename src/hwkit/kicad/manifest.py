"""Source manifest of the outputs: SHA-256 of each source file, the hwkit version and the number of boards.

The outputs are up to date if the manifest equals the manifest of the current sources. The outputs themselves are not hashed: kicad-cli writes time stamps into them.
"""

import hashlib
import json
from pathlib import Path

from .. import __version__


def sources(project):
    """Source files of the outputs: all schematic sheets, the board, the project file and the process rules file, if present."""
    files = [*project.sheets(), project.pcb, project.pro]
    dru = project.pro.with_suffix(".kicad_dru")
    return files + ([dru] if dru.exists() else [])


def current(project, boards, base):
    return {"hwkit": __version__, "boards": boards, "files": {Path(f).resolve().relative_to(Path(base).resolve()).as_posix(): hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in sources(project)}}


def write(path, project, boards):
    path = Path(path)
    path.write_text(json.dumps(current(project, boards, path.parent), indent=1, sort_keys=True) + "\n")


def check(path, project, boards):
    """Returns (lines, issues)."""
    path = Path(path)
    if not path.exists():
        return [], [f"no outputs manifest {path}; run the outputs"]
    stored, now = json.loads(path.read_text()), current(project, boards, path.parent)
    if stored == now:
        return [f"outputs: up to date ({path})"], []
    changed = sorted(k for k in stored["files"].keys() | now["files"].keys() if stored["files"].get(k) != now["files"].get(k))
    changed += [k for k in ("hwkit", "boards") if stored.get(k) != now.get(k)]
    return [], [f"outputs not up to date, changed: {', '.join(changed)}; run the outputs"]
