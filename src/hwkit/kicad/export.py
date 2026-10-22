"""KiCad outputs with kicad-cli and InteractiveHtmlBom: PDFs, renders, manufacturing files, BOM, order files, ERC and DRC."""

import csv
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from . import sexp

COPPER_TYPES = ("signal", "power", "mixed", "jumper")
BOARD_PDF_LAYERS = ("F.SilkS", "B.SilkS", "F.Fab", "B.Fab")
GERBER_LAYERS = ("F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "Edge.Cuts")


class Project:
    def __init__(self, pro):
        self.pro = Path(pro)
        self.name = self.pro.stem
        self.sch = self.pro.with_suffix(".kicad_sch")
        self.pcb = self.pro.with_suffix(".kicad_pcb")
        for f in (self.sch, self.pcb):
            if not f.exists():
                raise FileNotFoundError(f)

    def sheets(self):
        """Root schematic and all sub-sheet files, each once."""
        found, todo = [], [self.sch]
        while todo:
            f = todo.pop()
            if f in found:
                continue
            found.append(f)
            for s in sexp.children(sexp.load(f), "sheet"):
                for p in sexp.children(s, "property"):
                    if p[1] in ("Sheetfile", "Sheet file"):
                        todo.append(f.parent / p[2])
        return found

    def copper_layers(self):
        layers = sexp.child(sexp.load(self.pcb), "layers")
        return [n[1] for n in layers[1:] if len(n) > 2 and n[2] in COPPER_TYPES]


def _run(cmd):
    r = subprocess.run([str(c) for c in cmd], check=False, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r


def bom_columns(fields):
    """kicad-cli field list and labels. fields: {role: field name}."""
    names = list(fields.values())
    return ["Reference", "Value", "Footprint", *names, "${QUANTITY}", "${DNP}"], ["Refs", "Value", "Footprint", *names, "Qty", "DNP"]


def bom(lab, project, out_csv, fields):
    """Grouped BOM as CSV. Returns the rows."""
    cols, labels = bom_columns(fields)
    group = ["Value", "Footprint", fields["manufacturer"], fields["mpn"]]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    _run([lab["tools"]["kicad_cli"], "sch", "export", "bom", "--fields", ",".join(cols), "--labels", ",".join(labels), "--group-by", ",".join(group), "--ref-range-delimiter", "", "-o", out_csv, project.sch])
    with open(out_csv, newline="") as f:
        return list(csv.DictReader(f))


def erc_drc(lab, project, out_dir):
    """Error-level ERC and DRC violations (with schematic parity). Returns (lines, issues)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cli = lab["tools"]["kicad_cli"]
    erc, drc = out_dir / "erc.json", out_dir / "drc.json"
    _run([cli, "sch", "erc", "--format", "json", "--severity-error", "-o", erc, project.sch])
    _run([cli, "pcb", "drc", "--format", "json", "--severity-error", "--schematic-parity", "-o", drc, project.pcb])
    e = json.loads(erc.read_text())
    d = json.loads(drc.read_text())
    n_erc = sum(len(s.get("violations", [])) for s in e.get("sheets", []))
    n_drc = {k: len(d.get(k, [])) for k in ("violations", "unconnected_items", "schematic_parity")}
    lines = [f"ERC errors: {n_erc} ({erc})", f"DRC errors: {n_drc} ({drc})"]
    issues = ([f"{n_erc} ERC error(s)"] if n_erc else []) + [f"DRC {k}: {n}" for k, n in n_drc.items() if n]
    return lines, issues


def write_order_files(rows, fields, boards, out_dir):
    """Upload files for the DigiKey and Mouser BOM tools. DNP lines are left out. Quantity = BOM quantity × boards."""
    vendors = {
        "digikey": ["Customer Reference", "Quantity", "Manufacturer", "Manufacturer Part Number", "Product Link"],
        "mouser": ["Customer Part Number", "Quantity", "Manufacturer", "Mfr Part Number", "Product Link"],
    }
    paths = []
    for vendor, header in vendors.items():
        path = out_dir / f"order-{vendor}.csv"
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                if r["DNP"].strip():
                    continue
                w.writerow([r["Refs"], int(r["Qty"]) * boards, r[fields["manufacturer"]], r[fields["mpn"]], r[fields[vendor]]])
        paths.append(path)
    return paths


def ibom(lab, project, out_dir, fields):
    tools = lab["tools"]
    if not tools.get("ibom") or not Path(tools["ibom"]).exists():
        raise FileNotFoundError(f"InteractiveHtmlBom script not found: tools.ibom = {tools.get('ibom')!r}")
    extra = ",".join(fields[k] for k in ("manufacturer", "mpn"))
    _run([tools["kicad_python"], tools["ibom"], "--no-browser", "--dest-dir", out_dir.resolve(), "--name-format", f"{project.name}-ibom", "--extra-fields", extra, "--include-nets", "--include-tracks", project.pcb.resolve()])
    return out_dir / f"{project.name}-ibom.html"


def export_all(lab, project, out, fields, boards, rev):
    """All outputs below out/: docs/, manufacturing/, bom/. Returns the list of written files."""
    cli = lab["tools"]["kicad_cli"]
    docs, fab, bom_dir = out / "docs", out / "manufacturing", out / "bom"
    for d in (docs, fab, bom_dir):
        d.mkdir(parents=True, exist_ok=True)
    written = []

    sch_pdf = docs / f"{project.name}-schematic.pdf"
    _run([cli, "sch", "export", "pdf", "-o", sch_pdf, project.sch])
    board_pdf = docs / f"{project.name}-board.pdf"
    layers = project.copper_layers() + list(BOARD_PDF_LAYERS)
    _run([cli, "pcb", "export", "pdf", "--mode-multipage", "--include-border-title", "--layers", ",".join(layers), "--common-layers", "Edge.Cuts", "-o", board_pdf, project.pcb])
    written += [sch_pdf, board_pdf]
    for side in ("top", "bottom"):
        png = docs / f"{project.name}-{side}.png"
        _run([cli, "pcb", "render", "--side", side, "--quality", "high", "-o", png, project.pcb])
        written.append(png)

    gerbers = fab / "gerbers"
    if gerbers.exists():
        shutil.rmtree(gerbers)
    gerbers.mkdir()
    _run([cli, "pcb", "export", "gerbers", "--layers", ",".join(project.copper_layers() + list(GERBER_LAYERS)), "-o", gerbers, project.pcb])
    _run([cli, "pcb", "export", "drill", "--format", "excellon", "--generate-map", "--map-format", "pdf", "-o", gerbers, project.pcb])
    pos = fab / f"{project.name}-pos.csv"
    _run([cli, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--exclude-dnp", "-o", pos, project.pcb])
    archive = fab / f"{project.name}-v{rev}-gerbers.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gerbers.iterdir()):
            z.write(f, f.name)
    written += [archive, pos]

    rows = bom(lab, project, bom_dir / f"{project.name}-bom.csv", fields)
    written.append(bom_dir / f"{project.name}-bom.csv")
    written += write_order_files(rows, fields, boards, bom_dir)
    written.append(ibom(lab, project, bom_dir, fields))
    return written
