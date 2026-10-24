# AGENTS.md

Entry point for any coding agent. Claude Code reads `CLAUDE.md`, which refers here.

## Use in a hardware project
- Read the skill for the task before you start: `skills/<name>/SKILL.md`.
  - `kicad-project`: KiCad project workflow: template, checks, outputs, README, parts, release.
  - `enclosure-design`: case for a KiCad PCB.
  - `bambu-print-prep`: Bambu Studio print project, inlaid labels, slice verification.
  - `exploded-render`: Blender exploded views.
  - `partsbox`: PartsBox stock, project BOM, API key and MCP setup.
  - `retro`: move findings of a finished project into this toolkit and the project files.
- Design principles: `lessons.md`. Older and removed lessons: `lessons-archive.md`.
- Equipment and defaults: `lab/profile.toml` (`hwkit lab show`).
- Process rules for PCB manufacturers: `src/hwkit/fab/*.kicad_dru`.
- Code: package `hwkit`, command line `hwkit -h`.

## Rules for changes to this toolkit
- Concise wording. Every line must carry information.
- Knowledge goes into code first (fix the tool, add a check or a helper), then skills, then `lessons.md`.
- A check is code only if it is deterministic and always valid. A recommendation that the user can decide against goes into a skill.
- `lessons.md`: general design principles, one bullet each, at most 100 (`hwkit lessons check lessons.md`, also a test). No tool workarounds, no project items. Removed entries go to `lessons-archive.md`.
- Lab-specific values only in `lab/profile.toml`.
- Command output: a summary line, then `ISSUE:` and `NOTE:` lines only. Full reports go to files.
- Before a commit: `uv run --group dev pytest`. Release: update the version in `pyproject.toml`, `src/hwkit/__init__.py`, `.claude-plugin/plugin.json`; tag `vX.Y.Z`; push with tags.
- Projects pin a tag. Record behaviour changes in the tag message.
