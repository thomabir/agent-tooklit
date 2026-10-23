# AGENTS.md

Entry point for any coding agent. Claude Code reads `CLAUDE.md`, which refers here.

## Use in a hardware project
- Read the skill for the task before you start: `skills/<name>/SKILL.md`.
  - `kicad-project`: KiCad design rules, outputs, README, release.
  - `enclosure-design`: case for a KiCad PCB.
  - `bambu-print-prep`: Bambu Studio print project, inlaid labels, slice verification.
  - `exploded-render`: Blender exploded views.
  - `partsbox`: PartsBox MCP setup, stock lookup, project BOM.
  - `retro`: move findings of a finished project into this toolkit.
- Failure modes: `lessons.md` (ids L01, ...). Read the entries that the skill references.
- Equipment and defaults: `lab/profile.toml` (`hwkit lab show`).
- Code: package `hwkit`, command line `hwkit -h`.

## Rules for changes to this toolkit
- Concise wording. Every line must carry information.
- Knowledge goes into code first, then skills, then `lessons.md`.
- Every lesson: symptom, cause, proof, fix, source. Reference lessons by id from code and skills.
- Lab-specific values only in `lab/profile.toml`.
- Results of CLI slices are "slice verified", never "prints correctly" (L14).
- Before a commit: `uv run --group dev pytest`. Release: update the version in `pyproject.toml`, `src/hwkit/__init__.py`, `.claude-plugin/plugin.json`; tag `vX.Y.Z`; push with tags.
- Projects pin a tag. Record behaviour changes in the tag message.
