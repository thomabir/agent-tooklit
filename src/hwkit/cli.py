"""Command line: hwkit <group> <command>. Run "hwkit -h"."""

import argparse
import datetime
import json
import sys
from pathlib import Path

from . import lab as labmod


def _report(lines, issues):
    print("\n".join(lines))
    for i in issues:
        print(f"ISSUE: {i}")
    return 1 if issues else 0


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


def _project(a):
    from .kicad.export import Project

    return Project(a.project)


def _placed_rows(lab, project, work):
    """BOM rows without DNP lines, same parts merged."""
    from .kicad.export import bom, merge_by_part

    fields = lab["kicad"]["fields"]
    return merge_by_part(bom(lab, project, Path(work) / "bom.csv", fields), fields)


def _kicad_init(a, lab):
    from . import readme
    from .kicad.export import Project
    from .kicad.setup import rename, set_title_block

    pro = rename(a.project, a.name or a.id)
    project = Project(pro)
    title = f"{a.id} {a.title}"
    values = {"title": title, "date": datetime.date.today().isoformat(), "rev": a.rev, "company": lab["kicad"]["author"]}
    for f in [*project.sheets(), project.pcb]:
        f.write_text(set_title_block(f.read_text(), values))
        print(f"title block: {f}")
    if a.readme:
        p = Path(a.readme)
        p.write_text(readme.set_title(p.read_text(), title))
        print(f"title: {p}")
    print(f"project: {pro}")


def _kicad_fab_rules(a, lab):
    from .kicad.setup import copy_fab_rules, processes

    if a.process is None:
        print("\n".join(processes()))
        return 0
    print(f"process rules: {copy_fab_rules(a.project, a.process)}")


def _kicad_import_part(a, lab):
    from .kicad.setup import import_lcsc

    print(import_lcsc(a.project, a.lcsc_id, a.overwrite))


def _kicad_check(a, lab):
    from .kicad import checks, manifest, sexp
    from .kicad.export import bom, erc_drc
    from .kicad.setup import check_fab_rules

    k = lab["kicad"]
    project = _project(a)
    work = Path(a.work)
    blocks = {f.name: checks.title_block(sexp.load(f)) for f in project.sheets()}
    pcb = sexp.load(project.pcb)
    blocks[project.pcb.name] = checks.title_block(pcb)
    results = [
        checks.check_title_blocks(blocks, k.get("author"), k.get("id_pattern")),
        checks.check_board(pcb),
        check_fab_rules(lab, project, work),
        checks.check_bom(bom(lab, project, work / "bom.csv", k["fields"]), k["fields"]),
        erc_drc(lab, project, work),
    ]
    if a.outputs:
        results.append(manifest.check(Path(a.outputs) / "manifest.json", project, a.boards))
    return _report([line for r in results for line in r[0]], [i for r in results for i in r[1]])


def _kicad_outputs(a, lab):
    from .kicad import checks, manifest, sexp
    from .kicad.export import export_all

    project = _project(a)
    out = Path(a.out)
    path = out / "manifest.json"
    if not a.force and not manifest.check(path, project, a.boards)[1]:
        print(f"outputs up to date ({path}); --force to write them again")
        return 0
    rev = checks.title_block(sexp.load(project.pcb))["rev"]
    for f in export_all(lab, project, out, lab["kicad"]["fields"], a.boards, rev):
        print(f)
    manifest.write(path, project, a.boards)
    print(path)


def _kicad_order_files(a, lab):
    from .kicad.export import bom, write_order_files

    fields = lab["kicad"]["fields"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    project = _project(a)
    for f in write_order_files(bom(lab, project, out / f"{project.name}-bom.csv", fields), fields, a.boards, out):
        print(f)


def _kicad_fill_distributors(a, lab):
    from . import distributors
    from .kicad import fields as fieldsmod

    f = lab["kicad"]["fields"]
    mfr, mpn = f["manufacturer"], f["mpn"]
    project = _project(a)
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
            values = {f[role]: getattr(offer, attr) for role, attr in d.roles.items() if role in f and getattr(offer, attr)}
            match = lambda p, m=manufacturer, n=part: p.get(mfr, "") == m and p.get(mpn) == n
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


def _kicad_prices(a, lab):
    from . import distributors, prices

    f = lab["kicad"]["fields"]
    rows = _placed_rows(lab, _project(a), a.work)
    parts = sorted({(r[f["manufacturer"]], r[f["mpn"]], (r.get(f.get("digikey_pn", ""), ""), r.get(f.get("mouser_pn", ""), ""))) for r in rows if r[f["mpn"]].strip()})
    found, notes = distributors.configured(lab)
    for n in notes:
        print(f"NOTE: {n}")
    result, issues = prices.fetch(found, [(m, p, {"digikey": dk, "mouser": ms}) for m, p, (dk, ms) in parts])
    prices.write(a.out, result)
    print(f"{len(result)} price break(s) for {len(parts)} part(s): {a.out}")
    return _report([], issues)


def _readme_contents(a, lab):
    """Generated block contents from the KiCad project, or {} without a project."""
    if not a.project:
        return {}
    from .kicad import report, sexp
    from .prices import Prices

    project = _project(a)
    pcb = sexp.load(project.pcb)
    rows = _placed_rows(lab, project, a.work)
    return {
        "titleblock": report.board_summary(pcb, project.copper_layers()),
        "bom": report.bom_block(rows, lab["kicad"]["fields"], Prices(a.prices), a.boards, pcb),
    }


def _readme_update(a, lab):
    from . import readme

    p = Path(a.readme)
    old = p.read_text()
    text, missing = readme.update(old, _readme_contents(a, lab))
    if text != old:
        p.write_text(text)
    print(f"{'written' if text != old else 'up to date'}: {p}")
    return _report([], [f"README: no generated block '{n}'" for n in missing])


def _readme_check(a, lab):
    from . import readme
    from .kicad import checks, sexp

    p = Path(a.readme)
    text = p.read_text()
    expected = checks.title_block(sexp.load(_project(a).pcb))["title"] if a.project else None
    lines, issues = readme.check(text, a.release, expected)
    contents = _readme_contents(a, lab)
    new, missing = readme.update(text, contents)
    issues += [f"README: no generated block '{n}'" for n in missing]
    if new != text:
        stale = [n for n, c in readme.blocks(new).items() if c != readme.blocks(text).get(n)]
        issues.append(f"README: generated block(s) not up to date: {', '.join(stale)}; run the README update")
    return _report(lines, issues)


def _partsbox_stock(a, lab):
    from . import partsbox

    rows = _placed_rows(lab, _project(a), a.work)
    lines, notes = partsbox.stock_report(partsbox.Client(), rows, lab["kicad"]["fields"], a.boards)
    return _report(lines + [f"NOTE: {n}" for n in notes], [])


def _partsbox_project(a, lab):
    from . import partsbox
    from .kicad import checks, sexp

    project = _project(a)
    tb = checks.title_block(sexp.load(project.pcb))
    name = a.name or f"{tb['title']} v{tb['rev']}"
    rows = _placed_rows(lab, project, a.work)
    pid, created = partsbox.sync_project(partsbox.Client(), name, rows, lab["kicad"]["fields"])
    print(f"PartsBox project '{name}' ({pid}): {'created' if created else 'entries replaced'}, {len(rows)} entries")


def _lessons_check(a, lab):
    from . import lessons

    return _report(*lessons.check(Path(a.path)))


def _lab_show(a, lab):
    print(f"# {labmod.profile_path()}")
    print(json.dumps(lab, indent=1))


def _project_arg(c, required=True):
    if required:
        c.add_argument("project", help=".kicad_pro file")
    else:
        c.add_argument("--project", help=".kicad_pro file; without it, no generated blocks")


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

    k = groups.add_parser("kicad", help="KiCad project setup, checks and outputs").add_subparsers(required=True)
    c = k.add_parser("init", help="rename the project files and set the title blocks (and the README title)")
    _project_arg(c)
    c.add_argument("--id", required=True, help="project identifier, example PRJ-0123")
    c.add_argument("--title", required=True, help="title without the identifier")
    c.add_argument("--name", help="file name of the project; default: the identifier")
    c.add_argument("--rev", default="0.1")
    c.add_argument("--readme", help="README to set the level 1 heading in")
    c.set_defaults(func=_kicad_init)
    c = k.add_parser("fab-rules", help="copy a process rules file (.kicad_dru) from the library; without a process: list the library")
    _project_arg(c)
    c.add_argument("process", nargs="?")
    c.set_defaults(func=_kicad_fab_rules)
    c = k.add_parser("import-part", help="symbol, footprint and 3D model of an LCSC part into the project library lib/parts")
    _project_arg(c)
    c.add_argument("lcsc_id", help="LCSC part number, example C25804")
    c.add_argument("--overwrite", action="store_true")
    c.set_defaults(func=_kicad_import_part)
    c = k.add_parser("check", help="title blocks, outline, zones filled, process rules, BOM fields, ERC, DRC, outputs up to date")
    _project_arg(c)
    c.add_argument("--work", default="build/kicad-check", help="folder for BOM and ERC/DRC reports")
    c.add_argument("--outputs", help="outputs folder with manifest.json; check that the outputs are up to date")
    c.add_argument("--boards", type=int, default=1, help="number of boards of the outputs")
    c.set_defaults(func=_kicad_check)
    c = k.add_parser("outputs", help="PDFs, renders, Gerbers, positions, BOM, iBOM, order files; skipped if the sources did not change")
    _project_arg(c)
    c.add_argument("--out", default="outputs")
    c.add_argument("--boards", type=int, default=1, help="number of boards for the order files")
    c.add_argument("--force", action="store_true", help="write the outputs also if they are up to date")
    c.set_defaults(func=_kicad_outputs)
    c = k.add_parser("order-files", help="BOM, DigiKey and Mouser order files only")
    _project_arg(c)
    c.add_argument("--out", default="outputs/bom")
    c.add_argument("--boards", type=int, default=1, help="number of boards")
    c.set_defaults(func=_kicad_order_files)
    c = k.add_parser("fill-distributors", help="DigiKey, Mouser and datasheet fields from the distributor APIs, by Manufacturer and MPN")
    _project_arg(c)
    c.add_argument("--write", action="store_true", help="write the schematic files; without it: dry run")
    c.add_argument("--force", action="store_true", help="replace fields that are not empty")
    c.add_argument("--only", choices=["digikey", "mouser"])
    c.set_defaults(func=_kicad_fill_distributors)
    c = k.add_parser("prices", help="price breaks of the BOM parts from the distributor APIs into a price cache (CSV)")
    _project_arg(c)
    c.add_argument("--out", required=True, help="price cache CSV")
    c.add_argument("--work", default="build/kicad-prices")
    c.set_defaults(func=_kicad_prices)

    r = groups.add_parser("readme", help="project README: generated blocks and section check").add_subparsers(required=True)
    for name, func, text in (("update", _readme_update, "write the generated blocks"), ("check", _readme_check, "sections (content, TODO, N/A), title, generated blocks up to date")):
        c = r.add_parser(name, help=text)
        c.add_argument("readme")
        _project_arg(c, required=False)
        c.add_argument("--prices", default="", help="price cache CSV")
        c.add_argument("--boards", type=int, default=1, help="number of boards for the prices")
        c.add_argument("--work", default="build/readme")
        if name == "check":
            c.add_argument("--release", action="store_true", help="TODO is an issue")
        c.set_defaults(func=func)

    pb = groups.add_parser("partsbox", help="PartsBox stock and project").add_subparsers(required=True)
    c = pb.add_parser("stock", help="stock of the BOM parts; candidates from stock for the other lines")
    _project_arg(c)
    c.add_argument("--boards", type=int, default=1)
    c.add_argument("--work", default="build/partsbox")
    c.set_defaults(func=_partsbox_stock)
    c = pb.add_parser("project", help="create the PartsBox project '<title> v<rev>', or replace its entries with the BOM")
    _project_arg(c)
    c.add_argument("--name", help="project name; default: '<title> v<rev>'")
    c.add_argument("--work", default="build/partsbox")
    c.set_defaults(func=_partsbox_project)

    ls = groups.add_parser("lessons", help="lessons file").add_subparsers(required=True)
    c = ls.add_parser("check", help="number of entries")
    c.add_argument("path")
    c.set_defaults(func=_lessons_check)

    a = p.parse_args(argv)
    sys.exit(a.func(a, labmod.load()) or 0)


if __name__ == "__main__":
    main()
