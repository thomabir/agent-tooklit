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

    a = p.parse_args(argv)
    sys.exit(a.func(a, labmod.load()) or 0)


if __name__ == "__main__":
    main()
