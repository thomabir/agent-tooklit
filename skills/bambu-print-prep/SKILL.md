---
name: bambu-print-prep
description: Prepare and verify a Bambu Studio print project (3MF) from CadQuery parts, with optional inlaid multi-material labels. Use for any 3D-print preparation, slicer settings, Bambu 3MF, or "labels/gaps after slicing".
---

# Bambu print preparation

Toolkit: `github.com/thomabir/agent-tooklit`, local `~/code/agent-toolkit` (package `hwkit`). Lab equipment: `lab/profile.toml` (`hwkit lab show`).

## Setup in a project
- `uv add "hwkit @ git+https://github.com/thomabir/agent-tooklit@<tag>"` (pin a tag).
- `hwkit bambu flatten --out build/bambu-profiles`
- `hwkit bambu template --profiles build/bambu-profiles --out <project>/bambu-project-settings.json` and commit it. Regenerate after a Bambu Studio update or a lab profile change.

## Generator (project code)
- Parts in print orientation; labels face on the plate.
- Labels: `hwkit.labels` (`InlayRules(nozzle_d)`, `text`, `polarity_symbol`, `check_label`). Stop on `ValueError`.
- Inlay object: body part on filament 1, labels part on filament 2, `settings = hwkit.bambu.INLAY_OBJECT_SETTINGS`.
- Plate: `label_first_plate_settings(depth, template, 2, 1)`.
- Write with `hwkit.bambu.project.write_project()` through `hwkit.outputs.OutputGuard.write_all()`.
- All parts on one plate.

## Verify
`hwkit bambu verify <project.3mf> --labels <labels.stl> --body <body.stl> --out build/verify`

Report the printed values. Pass = "slice verified: all criteria met". This is not a print result.
After a change of the project format, ask the user to confirm key values in the GUI. The GUI applies only the keys in `different_settings_to_system`.

## Do not
- Verify with preset arguments: they replace the project settings.
- Edit the project template by hand.
- Overwrite a file that `OutputGuard` reports as changed; ask the user.
