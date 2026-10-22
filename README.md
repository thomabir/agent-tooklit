# agent-toolkit

> [!WARNING]
> **This repo is heavily vibecoded -- Use with care**

Reusable processes for hardware projects, for use by a human and an LLM agent.

| Path | Content |
| :--- | :--- |
| `src/hwkit/` | Python package and command line `hwkit` |
| `skills/` | Claude Code skills: procedures and acceptance criteria |
| `lessons.md` | Failure modes with cause, proof and fix (L01, ...) |
| `lab/profile.toml` | Lab equipment and defaults |
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
uv add "hwkit @ git+https://github.com/thomabir/agent-tooklit@v0.1.0"
```

## Commands

```sh
hwkit lab show
hwkit bambu flatten --out build/bambu-profiles
hwkit bambu template --profiles build/bambu-profiles --out bambu-project-settings.json
hwkit bambu verify <project.3mf> --labels <labels.stl> --body <body.stl> --out build/verify
hwkit bambu slice|check-project|check-gcode ...
```

## Tests

```sh
uv run --group dev pytest                    # unit tests
sh tests/reference_check.sh <44.006 folder>               # flatten, template, verify against the reference project
uv run python tests/reference_render.py <44.006 folder>   # render of the reference project
```

Reference check pass: template identical to the reference template, "slice verified: all criteria met". Run it after a Bambu Studio update.
