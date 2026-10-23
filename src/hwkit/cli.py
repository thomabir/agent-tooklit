"""Command line: hwkit <group> <command>. Run "hwkit -h"."""

import argparse
import json
import sys
from pathlib import Path

from . import lab as labmod


def _bambu_flatten(a, lab):
    from .bambu.presets import flatten

    print(f"flat presets: {flatten(lab, a.out)}")


def _bambu_template(a, lab):
    from .bambu.presets import make_template

    settings = make_template(lab, a.profiles, a.work)
    Path(a.out).write_text(json.dumps(settings, indent=4) + "\n")
    print(f"template: {a.out}")


def _bambu_slice(a, lab):
    from .bambu.slicer import slice_file

    r = slice_file(a.input, a.out, lab, profiles_dir=a.profiles, process_json=a.process)
    print(f"return code {r['return_code']}, {r['message']}, exit status {r['exit_status']}, log {r['log']}")
    return 0 if r["return_code"] == 0 else 1


def _report(lines, issues):
    print("\n".join(lines))
    for i in issues:
        print(f"ISSUE: {i}")
    return 1 if issues else 0


def _bambu_check_project(a, lab):
    from .bambu.checks import check_project, inlay_region

    if a.inlay_region:
        print(" ".join(f"{v:.2f}" for v in inlay_region(a.project)))
        return 0
    return _report(*check_project(a.project, plate_first_layer=a.first_layer))


def _bambu_check_gcode(a, lab):
    from .bambu.checks import check_gcode_settings

    return _report(*check_gcode_settings(a.gcode, a.project, extra_keys=lab["process"].get("choices", {}).keys()))


def _bambu_verify(a, lab):
    from .bambu.verify import verify

    issues = verify(a.project, a.labels, a.body, a.out, lab)
    for i in issues:
        print(f"ISSUE: {i}")
    print("slice verified: all criteria met" if not issues else f"{len(issues)} issue(s)")
    return 1 if issues else 0


def _kicad_check(a, lab):
    from .kicad import checks, sexp
    from .kicad.export import Project, bom, erc_drc

    k = lab["kicad"]
    project = Project(a.project)
    work = Path(a.work)
    blocks = {f.name: checks.title_block(sexp.load(f)) for f in project.sheets()}
    pcb = sexp.load(project.pcb)
    blocks[project.pcb.name] = checks.title_block(pcb)
    results = [
        checks.check_title_blocks(blocks, k.get("author")),
        checks.check_board(pcb, k["gnd_nets"], k["mounting_hole_grid"], k["corner_max_turn"], blocks[project.pcb.name]),
        checks.check_bom(bom(lab, project, work / "bom.csv", k["fields"]), k["fields"]),
        erc_drc(lab, project, work),
    ]
    return _report([line for r in results for line in r[0]], [i for r in results for i in r[1]])


def _kicad_outputs(a, lab):
    from .kicad import checks, sexp
    from .kicad.export import Project, export_all

    project = Project(a.project)
    rev = checks.title_block(sexp.load(project.pcb))["rev"]
    for f in export_all(lab, project, Path(a.out), lab["kicad"]["fields"], a.boards, rev):
        print(f)


def _kicad_order_files(a, lab):
    from .kicad.export import Project, bom, write_order_files

    fields = lab["kicad"]["fields"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    project = Project(a.project)
    for f in write_order_files(bom(lab, project, out / f"{project.name}-bom.csv", fields), fields, a.boards, out):
        print(f)


def _kicad_fill_distributors(a, lab):
    from . import distributors
    from .kicad import fields as fieldsmod
    from .kicad.export import Project

    f = lab["kicad"]["fields"]
    mfr, mpn = f["manufacturer"], f["mpn"]
    project = Project(a.project)
    texts = {s: s.read_text() for s in project.sheets()}
    parts = sorted({(p.get(mfr, ""), p[mpn]) for t in texts.values() for p in fieldsmod.placed(t) if p.get(mpn, "").strip()})
    found, notes = distributors.configured(lab)
    for n in notes:
        print(f"NOTE: {n}")
    issues, changed = [], 0
    for manufacturer, part in parts:
        for d in found:
            if a.only and d.name != a.only:
                continue
            try:
                offer, note = d.lookup(manufacturer, part)
            except RuntimeError as e:
                issues.append(f"{d.name}: {manufacturer} {part}: {e}")
                continue
            if offer is None:
                issues.append(f"{d.name}: {manufacturer} {part}: {note}")
                continue
            price = f"{offer.unit_price:.2f} {offer.currency}" if offer.unit_price is not None else "no price"
            print(f"{d.name}: {manufacturer} {part} -> {offer.part_number} ({offer.package}), stock {offer.stock}, {price} at qty 1, {note}, {offer.url}")
            values = {f[role]: getattr(offer, attr) for role, attr in d.roles.items()}
            match = lambda p: p.get(mfr, "") == manufacturer and p.get(mpn) == part
            for sheet, text in texts.items():
                texts[sheet], n, conflicts = fieldsmod.set_fields(text, match, values, after=mpn, replace=a.force)
                changed += n
                issues += sorted({f"{d.name}: {part}: field '{k}' is {old!r}, API gives {new!r} (use --force)" for k, old, new in conflicts})
    if a.write:
        for sheet, text in texts.items():
            if text != sheet.read_text():
                sheet.write_text(text)
                print(f"written: {sheet}")
    print(f"{changed} field change(s){'' if a.write else ' (dry run, use --write)'}")
    return _report([], issues)


def _lab_show(a, lab):
    print(f"# {labmod.profile_path()}")
    print(json.dumps(lab, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(prog="hwkit")
    groups = p.add_subparsers(required=True)

    g = groups.add_parser("lab", help="lab profile").add_subparsers(required=True)
    g.add_parser("show").set_defaults(func=_lab_show)

    b = groups.add_parser("bambu", help="Bambu Studio presets, slicing, checks").add_subparsers(required=True)
    c = b.add_parser("flatten", help="flat presets for the command line")
    c.add_argument("--out", required=True)
    c.set_defaults(func=_bambu_flatten)
    c = b.add_parser("template", help="project settings template (JSON)")
    c.add_argument("--profiles", required=True, help="folder from 'flatten'")
    c.add_argument("--out", required=True)
    c.add_argument("--work", default="build/bambu-template")
    c.set_defaults(func=_bambu_template)
    c = b.add_parser("slice", help="command-line slice; without --profiles: project mode")
    c.add_argument("input")
    c.add_argument("out")
    c.add_argument("--profiles")
    c.add_argument("--process")
    c.set_defaults(func=_bambu_slice)
    c = b.add_parser("check-project", help="objects, filaments, per-object and plate settings")
    c.add_argument("project")
    c.add_argument("--first-layer", default="2 1", help="expected first_layer_print_sequence")
    c.add_argument("--inlay-region", action="store_true", help="print only the plate region of the inlay object")
    c.set_defaults(func=_bambu_check_project)
    c = b.add_parser("check-gcode", help="G-code header against project settings")
    c.add_argument("gcode")
    c.add_argument("project")
    c.set_defaults(func=_bambu_check_gcode)
    c = b.add_parser("verify", help="full slice verification of a project with inlaid labels")
    c.add_argument("project")
    c.add_argument("--labels", required=True, help="labels STL, print orientation")
    c.add_argument("--body", required=True, help="body STL with the inlay pockets, print orientation")
    c.add_argument("--out", required=True)
    c.set_defaults(func=_bambu_verify)

    k = groups.add_parser("kicad", help="KiCad project checks and outputs").add_subparsers(required=True)
    c = k.add_parser("check", help="title blocks, outline, mounting holes, ground pour, BOM fields, ERC, DRC")
    c.add_argument("project", help=".kicad_pro file")
    c.add_argument("--work", default="build/kicad-check", help="folder for BOM and ERC/DRC reports")
    c.set_defaults(func=_kicad_check)
    c = k.add_parser("outputs", help="schematic and board PDFs, renders, Gerbers, drill, positions, BOM, iBOM, order files")
    c.add_argument("project", help=".kicad_pro file")
    c.add_argument("--out", default="outputs")
    c.add_argument("--boards", type=int, default=1, help="number of boards for the order files")
    c.set_defaults(func=_kicad_outputs)
    c = k.add_parser("order-files", help="BOM, DigiKey and Mouser order files only")
    c.add_argument("project", help=".kicad_pro file")
    c.add_argument("--out", default="outputs/bom")
    c.add_argument("--boards", type=int, default=1, help="number of boards")
    c.set_defaults(func=_kicad_order_files)
    c = k.add_parser("fill-distributors", help="DigiKey and Mouser fields from the distributor APIs, by Manufacturer and MPN")
    c.add_argument("project", help=".kicad_pro file")
    c.add_argument("--write", action="store_true", help="write the schematic files; without it: dry run")
    c.add_argument("--force", action="store_true", help="replace fields that are not empty")
    c.add_argument("--only", choices=["digikey", "mouser"])
    c.set_defaults(func=_kicad_fill_distributors)

    a = p.parse_args(argv)
    sys.exit(a.func(a, labmod.load()) or 0)


if __name__ == "__main__":
    main()
