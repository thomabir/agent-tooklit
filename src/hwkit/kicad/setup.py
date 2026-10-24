"""Project setup by text edits: title blocks, file names, process rules, library parts from LCSC."""

import base64
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import zstandard

from .export import _run
from .fields import _close, _quote

FAB_DIR = Path(__file__).resolve().parent.parent / "fab"
PROJECT_SUFFIXES = (".kicad_pro", ".kicad_sch", ".kicad_pcb", ".kicad_dru", ".kicad_prl")
EASYEDA2KICAD = "easyeda2kicad==1.0.1"
LIBRARY = "parts"  # nickname of the project library for imported parts


def set_title_block(text, values):
    """Set title block fields (title, date, rev, company) in .kicad_sch or .kicad_pcb text. Missing fields are added."""
    start = text.find("(title_block")
    if start < 0:
        raise ValueError("no title_block node")
    end = _close(text, start)
    node = text[start:end]
    for key, value in values.items():
        pattern = re.compile(rf'\({key} "((?:[^"\\]|\\.)*)"\)')
        new = f'({key} "{_quote(value)}")'
        if pattern.search(node):
            node = pattern.sub(lambda _, n=new: n, node, count=1)
        else:
            node = node[:-1].rstrip() + f"\n\t\t{new}\n\t)"
    return text[:start] + node + text[end:]


def rename(pro, name):
    """Rename all project files <stem>.<suffix> to <name>.<suffix>. Returns the new .kicad_pro path."""
    pro = Path(pro)
    if pro.stem == name:
        return pro
    for suffix in PROJECT_SUFFIXES:
        old = pro.with_suffix(suffix)
        if old.exists():
            old.rename(old.with_name(name + suffix))
    new = pro.with_name(name + ".kicad_pro")
    data = json.loads(new.read_text())
    data.setdefault("meta", {})["filename"] = new.name
    new.write_text(json.dumps(data, indent=2) + "\n")
    return new


def processes():
    return sorted(p.stem for p in FAB_DIR.glob("*.kicad_dru"))


def copy_fab_rules(pro, process):
    if process not in processes():
        raise ValueError(f"unknown process {process!r}; known: {', '.join(processes())}")
    dst = Path(pro).with_suffix(".kicad_dru")
    shutil.copyfile(FAB_DIR / f"{process}.kicad_dru", dst)
    return dst


CANARY_TEXT = '(gr_text "hwkit canary" (at 0 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))'
CANARY_RULE = '\n(rule "hwkit canary"\n\t(layer "?.Silkscreen")\n\t(constraint text_height (min 100mm)))\n'


def rules_load(lab, pcb, dru, work):
    """True if KiCad loads the rules file. KiCad ignores a rules file with a syntax error without a message.
    Test: DRC of a copy of the board with a test text and a test rule that the text violates."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    board = Path(pcb).read_text().rstrip()
    (work / "canary.kicad_pcb").write_text(board[: board.rindex(")")] + CANARY_TEXT + "\n)\n")
    (work / "canary.kicad_dru").write_text(Path(dru).read_text() + CANARY_RULE)
    report = work / "canary-drc.json"
    _run([lab["tools"]["kicad_cli"], "pcb", "drc", "--format", "json", "-o", report, work / "canary.kicad_pcb"])
    return any(v.get("type") == "text_height" for v in json.loads(report.read_text()).get("violations", []))


def check_fab_rules(lab, project, work):
    """Returns (lines, issues): the process of the rules file, if it differs from the library, and if KiCad loads it."""
    dru = project.pro.with_suffix(".kicad_dru")
    if not dru.exists():
        return [], [f"no process rules file {dru.name}; copy one with fab-rules ({', '.join(processes())})"]
    text = dru.read_text()
    issues = [] if rules_load(lab, project.pcb, dru, Path(work) / "rules") else [f"{dru.name}: KiCad does not load the rules file (syntax error); open Board Setup > Custom Rules for the error"]
    m = re.search(r"^# process: (\S+)", text, re.MULTILINE)
    if not m:
        return [f"process rules: {dru.name}, not from the library"], issues
    lib = FAB_DIR / f"{m.group(1)}.kicad_dru"
    same = lib.exists() and lib.read_text() == text
    return [f"process rules: {m.group(1)}" + ("" if same else " (differs from the library version)")], issues


def _ensure_lib_table(path, kind, uri):
    """Add the project library to sym-lib-table or fp-lib-table if not present."""
    entry = f'  (lib (name "{LIBRARY}")(type "KiCad")(uri "{uri}")(options "")(descr "Imported parts"))'
    if path.exists():
        text = path.read_text()
        if f'(name "{LIBRARY}")' in text:
            return
        text = text.rstrip().removesuffix(")").rstrip() + "\n" + entry + "\n)\n"
    else:
        text = f"({kind}\n  (version 7)\n{entry}\n)\n"
    path.write_text(text)


def import_lcsc(pro, lcsc_id, overwrite=False):
    """Symbol, footprint and 3D model of an LCSC part into the project library lib/parts.* with easyeda2kicad (pinned version, run with uvx).
    The STEP model is embedded in the footprint, so the board carries it. Returns the command output."""
    kicad_dir = Path(pro).resolve().parent
    lib = kicad_dir / "lib"
    lib.mkdir(exist_ok=True)
    cmd = ["uvx", "--from", EASYEDA2KICAD, "easyeda2kicad", "--full", "--lcsc_id", lcsc_id, "--output", str(lib / f"{LIBRARY}.kicad_sym"), "--project-relative"]  # absolute path: --project-relative needs it inside the working directory
    if overwrite:
        cmd.append("--overwrite")
    r = subprocess.run(cmd, check=False, cwd=kicad_dir, capture_output=True, text=True)
    out = r.stdout + r.stderr
    if r.returncode != 0 or "[ERROR]" in out:
        raise RuntimeError(f"{' '.join(cmd)}\n{out}")
    _ensure_lib_table(kicad_dir / "sym-lib-table", "sym_lib_table", f"${{KIPRJMOD}}/lib/{LIBRARY}.kicad_sym")
    _ensure_lib_table(kicad_dir / "fp-lib-table", "fp_lib_table", f"${{KIPRJMOD}}/lib/{LIBRARY}.pretty")
    shapes = lib / f"{LIBRARY}.3dshapes"
    for fp in sorted((lib / f"{LIBRARY}.pretty").glob("*.kicad_mod")):
        if embed_models(fp, shapes):
            out += f"embedded 3D model: {fp.name}\n"
    if shapes.exists():
        shutil.rmtree(shapes)
    return out


_MODEL_PATH = re.compile(r'\(model "\$\{KIPRJMOD\}/lib/[^"/]+\.3dshapes/([^"/]+)\.\w+"')


def embedded_files_node(name, data, file_type="model"):
    """KiCad (embedded_files ...) node: zstd (level 15), base64 in lines of 76 characters between "|", SHA-256 of the data as checksum (KiCad reads 64-character checksums as SHA-256)."""
    encoded = base64.b64encode(zstandard.ZstdCompressor(level=15).compress(data)).decode()
    lines = [encoded[i : i + 76] for i in range(0, len(encoded), 76)]
    body = "\n".join(("|" if i == 0 else " ") + line + ("|" if i == len(lines) - 1 else "") for i, line in enumerate(lines))
    return f'(embedded_files\n\t\t(file\n\t\t\t(name "{_quote(name)}")\n\t\t\t(type {file_type})\n\t\t\t(data\n{body}\n\t\t\t)\n\t\t\t(checksum "{hashlib.sha256(data).hexdigest()}")\n\t\t)\n\t)'


def embed_models(fp, shapes):
    """Embed the STEP model of a footprint from the folder shapes and point the model path to it. Returns True if the footprint changed."""
    text = fp.read_text()
    m = _MODEL_PATH.search(text)
    if not m or "(embedded_files" in text:
        return False
    step = shapes / f"{m.group(1)}.step"
    if not step.exists():
        return False
    text = text[: m.start()] + f'(model "kicad-embed://{step.name}"' + text[m.end() :]
    end = text.rstrip().rindex(")")
    fp.write_text(text[:end].rstrip() + "\n\t" + embedded_files_node(step.name, step.read_bytes()) + "\n)\n")
    return True
