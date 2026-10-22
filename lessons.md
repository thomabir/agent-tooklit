# Lessons

One entry per finding: symptom, cause, proof, fix. Newest last. Reference an entry by its id (L01, ...).
Source project: path or repository and commit.

## L01 Inlaid labels: strokes too narrow
- Symptom: labels with gaps after slicing, all nozzles 0.2 to 0.6 mm.
- Cause: Arial Bold 3–4 mm has strokes of approx. 0.5 mm.
- Proof: morphological opening with 2 × nozzle removes whole strokes.
- Fix: `hwkit.labels.check_label()`; Arial Black 7–10 mm for a 0.6 mm nozzle.

## L02 Inlaid labels: letter spacing and counters too narrow
- Symptom: neighbouring glyphs merge; islands of body material inside glyphs stay empty.
- Cause: font spacing < 2 × nozzle; counters approx. 1.4 mm.
- Fix: `hwkit.labels.text()` places glyphs `min_gap` apart; gap rule `min_gap = 2 × nozzle + 0.3 mm`.

## L03 3MF from CadQuery: mesh without shared vertices
- Symptom: slicer fills label regions with distorted shapes.
- Cause: `Shape.tessellate()` gives each face its own vertices; the slicer repairs the "open" mesh. trimesh merges vertices on load and reports watertight.
- Fix: `hwkit.bambu.project.indexed_mesh()`. STL is not affected.

## L04 Classic wall generator leaves gaps in narrow strokes
- Symptom: stroke = one wall loop + broken gap infill.
- Cause: stroke width not a multiple of the line width.
- Proof: layer-1 gaps > 0.2 mm 6.3 mm² (classic) → 1.5 mm² (Arachne), one filament.
- Fix: per-object `wall_generator = arachne` (`INLAY_OBJECT_SETTINGS`).

## L05 Elephant-foot compensation opens a gap at label boundaries
- Cause: label and body contours shrink separately on layer 1.
- Proof: with Arachne, gaps 1.5 → 0.03 mm² (one filament).
- Fix: per-object `elefant_foot_compensation = 0`.

## L06 Command line does not resolve preset inheritance
- Fix: `hwkit.bambu.presets.flatten()` merges the `inherits` chain.

## L07 Start G-code is in separate template files
- Symptom: flat preset has generic start G-code (homing, purge line at 205 °C, no `M620`); a project made from it carries that G-code.
- Cause: `<preset> template <key>.json` files are not in the `inherits` chain.
- Proof: after the fix, all `*_gcode` keys equal a GUI-saved project.
- Fix: `load_preset()` applies the template files; `make_template()` checks the G-code keys.

## L08 Filament order per layer
- Symptom: layer 1 prints body before labels.
- Cause: default order minimises filament changes.
- Fix: plate `first_layer_print_sequence = "2 1"` (space-separated; `"2,1"` has no effect), `other_layers_print_sequence = "2 <n> 2 1"`, `other_layers_print_sequence_nums = "1"`. Effect on quality not measured.

## L09 Generated file overwritten, or overwrites a user file
- Symptom: a project in `out/` changed outside the generator; origin unknown.
- Fix: `hwkit.outputs.OutputGuard`. Keep user-saved projects in a commit of their own.

## L10 Project 3MF needs project_settings.config with correct list lengths
- Symptom: CLI segmentation fault, or "Failed slicing", or "Flush volumes matrix do not match to the correct size!".
- Cause: missing `Metadata/project_settings.config`; per-filament lists with one entry; flush matrix not n × n.
- Fix: `make_template()`. Per-filament keys: `filament_*`, all keys of the filament presets, `default_filament_colour`, `pre_start_fan_time`.

## L11 GUI ignores project values not listed in different_settings_to_system
- Symptom: project has gyroid, GUI shows grid.
- Cause: GUI applies only listed keys over the system preset (CLI uses the project value in both cases).
- Fix: `make_template()` lists each preset key of `lab.process.choices`. Confirmed in the GUI by the user.

## L12 Preset arguments replace project settings in the CLI
- Symptom: verification slice used grid while the project had gyroid.
- Fix: verify in project mode (`slice_file()` without `profiles_dir`); compare the G-code header (`check_gcode_settings()`).

## L13 G-code parsing
- G2/G3 arcs must be interpolated.
- Filament change = `M620 S<n>A` (n from 0; 255 = unload). `T1000`, `T1100` are toolhead commands.
- Exclude prime tower and skirt; with several objects, restrict to the object region before the alignment.

## L14 Claims about print results
- A CLI slice and a G-code analysis give "slice verified", not "prints correctly". Only a print shows quality.
- Do not attribute a defect to a user action before the file content proves it.

## L15 KiCad top-view frame is left-handed with z up
- Symptom: connectors mirrored in the case (IN/OUT swapped) if the README frame is used directly.
- Fix: build the case in the STEP frame rotated 180° about z (`hwkit.fit.kicad_rotated_frame()`, `hwkit.render.kicad_glb_matrix()`).

## L16 Blender background render
- Freestyle needs a lineset with a linestyle, else a Python error in each render.
- KiCad GLB is in metres in the STEP frame.

## L17 Snap hook does not latch
- Symptom: weak snap; hooks stop short of the windows; lid pulls off without pressing the hooks.
- Cause: vertical latch clearance (hook retention face to window top) 0.1 mm, layer height 0.3 mm. The lid stop surfaces and the latch surfaces are rounded to layer boundaries; each of the 4 surfaces can move by up to ½ layer. Overhang sag of the window top and of the retention face adds to this.
- Proof: G-code (0.3 mm layers): base shoulder at z = 8.9 mm, lid skirt bottom at z = 8.8 mm (design 8.75 mm both). The lid sits 0.1 mm high; this is the full clearance. Overhang sag not measured.
- Fix: vertical latch clearance ≥ 2 × layer height. Check with `hwkit.fit.report(..., latches=..., latch_margin=2 × layer height)`. Put the latch and stop surfaces on layer boundaries of their part.
