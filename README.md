# agent-toolkit

> [!WARNING]
> **This repo is heavily vibecoded -- Use with care**

Reusable processes for hardware projects, for use by a human and an LLM agent.

| Path | Content |
| :--- | :--- |
| `src/hwkit/` | Python package and command line `hwkit` |
| `skills/` | Claude Code skills: procedures and acceptance criteria |
| `lessons.md` | General design principles, at most 100 |
| `lessons-archive.md` | Removed and older lessons |
| `lab/profile.toml` | Lab equipment and defaults |
| `src/hwkit/fab/` | PCB process rules (`.kicad_dru`) |
| `AGENTS.md` | Entry point for agents other than Claude Code |
| `tests/` | Tests |

## Install

Claude Code plugin (skills):

```
/plugin marketplace add thomabir/agent-tooklit
/plugin install agent-toolkit@thomabir
```

Other agents: see `AGENTS.md`.

Python package in a project (pin a tag):

```sh
uv add "hwkit @ git+https://github.com/thomabir/agent-tooklit@v0.7.1"
```

KiCad projects: start from the project template `kicad-prj-template`. Its Makefile calls `hwkit` (`make help`).

## Example

Plate with inlaid label → Bambu project → slice verification. Full script: `examples/inlay_lid.py`.

```python
from hwkit import lab, labels
from hwkit.bambu import INLAY_OBJECT_SETTINGS
from hwkit.bambu.project import label_first_plate_settings, write_project
from hwkit.outputs import OutputGuard

LAB = lab.load()
RULES = labels.InlayRules(nozzle_d=LAB["printer"]["nozzle_d"])
plate = cq.Workplane().box(40, 30, 3).translate((0, 0, 1.5))
label = labels.text("OUT", 7.0, 0, 0, 3.0, RULES, LAB["tools"]["label_font"])
labels.check_label("OUT", label, RULES, (-18, 18, -13, 13))   # ValueError if not printable
plate = plate.cut(label)
# flip both to print orientation, then:
write_project(path, [{"name": "lid", "parts": [("lid", plate_p, 1), ("labels", label_p, 2)],
                      "settings": INLAY_OBJECT_SETTINGS, "center": (128, 128)}],
              label_first_plate_settings(RULES.depth, template, 2, 1), template)
```

```sh
uv run hwkit bambu flatten --out build/example/profiles
uv run hwkit bambu template --profiles build/example/profiles --out build/example/bambu-project-settings.json --work build/example/template
uv run python examples/inlay_lid.py
uv run hwkit bambu verify build/example/out/lid.3mf --labels build/example/out/labels.stl --body build/example/out/lid.stl --out build/example/verify
```

Expected last line: `slice verified: all criteria met`. Coverage plot: `build/example/verify/coverage.png`.

Agent use: ask Claude Code for "a case for this KiCad board" or "prepare the print"; the plugin loads the matching skill.

## Commands

```sh
hwkit lab show
hwkit kicad init|fab-rules|import-part|check|outputs|order-files|fill-distributors|prices ...
hwkit readme update|check README.md --project <project.kicad_pro> --prices <prices.csv> --boards <n>
hwkit partsbox stock|project <project.kicad_pro>   # stock --out <bom folder>: stock.csv, order-digikey-against-stock.csv
hwkit lessons check lessons.md
hwkit bambu flatten --out build/bambu-profiles
hwkit bambu template --profiles build/bambu-profiles --out bambu-project-settings.json
hwkit bambu verify <project.3mf> --labels <labels.stl> --body <body.stl> --out build/verify
hwkit bambu slice|check-project|check-gcode ...
```

## Tests

```sh
uv run --group dev pytest                    # unit tests
sh tests/reference_check.sh <project folder>               # flatten, template, verify against a reference project
uv run python tests/reference_render.py <project folder>   # render of a reference project
```

Reference check pass: template identical to the reference template, "slice verified: all criteria met". Run it after a Bambu Studio update.
