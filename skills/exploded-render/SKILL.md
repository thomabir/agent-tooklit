---
name: exploded-render
description: Render exploded views of CadQuery/STL parts with a KiCad PCB (GLB) in Blender background mode. Use when the user wants a quick visual check of an assembly.
---

# Exploded render

```python
from hwkit import lab, render
render.exploded(lab.load(), "out", "render-exploded",
    parts=[{"stl": "out/assembly-base.stl", "rgba": [0.1, 0.11, 0.12, 1], "z": 0},
           {"stl": "out/assembly-lid.stl", "rgba": [0.1, 0.11, 0.12, 1], "z": 52}],
    glb={"path": "out/pcb-assembly.glb", "matrix": render.kicad_glb_matrix(pcb_w, pcb_t, z=22)})
```

- Parts in the assembled case frame; `z` = explode offset in mm.
- Output: one PNG per view and `<name>.png` with all views side by side.
- Look at the image before you report it. Check connector sides against the PCB (L15).
- Failure modes: L16.
