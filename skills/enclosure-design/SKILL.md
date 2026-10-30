---
name: enclosure-design
description: Design a 3D-printed enclosure for a KiCad PCB in CadQuery (snap fit, connector cut-outs, standoffs, inlaid labels) and check the fit against the KiCad STEP. Use when a PCB project needs a case.
---

# Enclosure design

Toolkit: `github.com/thomabir/agent-tooklit`, local `~/code/agent-toolkit` (package `hwkit`).

## Inputs
- PCB STEP and GLB: `kicad-cli pcb export step|glb --subst-models --force -o <file> <board>.kicad_pcb` (path in `lab/profile.toml`).
- Component positions and heights: read them from the STEP (bounding boxes, cylinder axes), not only from the README.

## Frame
- Case frame = KiCad STEP frame rotated 180° about z: x right seen from the front, y to the rear, z up from the PCB top. The KiCad top view is mirrored relative to this frame.
- `hwkit.fit.kicad_rotated_frame(pcb_w, pcb_t)`.

## Design rules (from the reference)
- Split at a connector axis; connector holes split between base and lid; PCB drops in vertically.
- Lap joint: lid skirt outside, base lip inside, 0.15 mm lateral clearance.
- Standoffs with locating pins in the base, hold-down posts in the lid.
- Cantilever snap hooks on the lid into base windows; bending strain ≤ approx. 1.3 % (`1.5 t y / L²`). Vertical arms print with layers across the bend.
- Preloaded hooks for a case without play: 45° retention face, window top below the contact line, so that each seated arm stays bent inwards (reference: 0.5 mm with the lid on the seam, ≥ 0.2 mm with the lid on the PCB). The 45° face pulls the lid down onto the PCB. The lid comes off with a firm pull.
- Lid posts end on the first lid layer boundary at or below the PCB top: the lid sits on the PCB and clamps it onto the standoffs.
- 90° hooks (release through the windows only): vertical latch clearance ≥ 2 × layer height. This clearance is play of the lid and of the PCB.
- Put the latch surfaces and the lid stop surfaces on layer boundaries, measured from the plate face of their part.
- Before the full print: test print of one hook and its window.
- Collars behind panel connectors take the plug force.
- Labels on the face that prints on the plate (see bambu-print-prep).

## Verify
- `hwkit.fit.report(base, lid, pcb, flexing=hook_arms, latches=hooks_90deg, latch_margin=2 * layer_height)`: no interference except "expected" at flexing features.
- Preloaded hooks: lid in its seat (on the PCB), `hwkit.fit.report(base, lid, pcb, flexing=hook_arms, preloaded=hook_arms)`. Check the preload range in the generator and stop on `ValueError`.
- Render: see exploded-render.
- Print preparation: see bambu-print-prep.
