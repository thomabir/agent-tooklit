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
- Layers with labels print with low speed and acceleration: `settings, layer_range, layer_gcode = slow_label_layers(depth, template)`. Pass `settings` and `layer_gcode=layer_gcode` to `write_project()`, and `"layer_ranges": [layer_range]` in each object.
- Label strokes narrower than 2 × nozzle diameter (Bambu Studio text in an Arachne object) print as single lines. They stay on the plate only on a clean plate and on slow layers.

## Before each print (tell the user)
- Clean the build plate: warm water and dish soap, then dry. Do not touch the print area. Grease from fingers stops adhesion of narrow lines at some plate positions only.
- After a print defect, ask about the plate condition before you change settings.
- Write with `hwkit.bambu.project.write_project()` through `hwkit.outputs.OutputGuard.write_all()`.
- All parts on one plate.

## Verify
`hwkit bambu verify <project.3mf> --labels <labels.stl> --body <body.stl> --out build/verify`

Report the printed values. Pass = "slice verified: all criteria met". This is not a print result.
The verification also checks the largest extrusion feed rate and the M201 acceleration limit on the layers with labels.
After a change of the project format, ask the user to confirm key values in the GUI. The GUI applies only the keys in `different_settings_to_system`.

## Do not
- Verify with preset arguments: they replace the project settings.
- Edit the project template by hand.
- Overwrite a file that `OutputGuard` reports as changed; ask the user.
