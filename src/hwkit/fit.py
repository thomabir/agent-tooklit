"""Interference check of case parts against a KiCad STEP export, assembled and along vertical assembly paths."""

import cadquery as cq
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

MIN_VOLUME = 1e-3  # mm3, numerical noise
PATH_STEPS = (0.5, 2, 4, 6, 8, 12, 16, 20, 30)  # mm


def kicad_rotated_frame(pcb_w, pcb_t, origin=(100.0, -100.0)):
    """Transform: KiCad STEP frame -> case frame rotated 180° about z (x right seen from the front, y to the rear). origin = front-left PCB corner in the STEP top view."""

    def transform(shape):
        return shape.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 180).translate(cq.Vector(pcb_w + origin[0], origin[1], -pcb_t))

    return transform


def load_step_components(path, transform=lambda s: s):
    """{reference: Shape} of the top-level components of a KiCad STEP. The board itself is "PCB"."""
    doc = TDocStd_Document(TCollection_ExtendedString("pcb"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    reader.ReadFile(str(path))
    reader.Transfer(doc)
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    tool.GetFreeShapes(roots)
    comps = TDF_LabelSequence()
    tool.GetComponents_s(roots.Value(1), comps)
    parts = {}
    for i in range(1, comps.Length() + 1):
        lab = comps.Value(i)
        name = TDataStd_Name()
        key = name.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), name) else f"part{i}"
        parts["PCB" if key.startswith("=>") else key] = transform(cq.Shape.cast(tool.GetShape_s(lab)))
    return parts


def _overlap(a, b):
    v = a.intersect(b)
    return v.Volume() if v is not None else 0.0


def report(base, lid, pcb, flexing=None, latches=None, latch_margin=0.0):
    """Print interference: assembled, PCB path into base, lid path onto base, latch clearance. flexing: lid features allowed to touch the base on the path (snap hooks).

    latches: lid hooks with a 90° retention face. With the lid latch_margin above its seat, they must not touch the base (L17).
    Returns the list of unexpected interferences.
    """
    if latch_margin < 0:
        raise ValueError("latch_margin must be >= 0")
    bad = []

    def check(title, pairs):
        hits = [(n, v) for n, v in pairs if v > MIN_VOLUME]
        print(f"{title}: {'no interference' if not hits else ''}")
        for n, v in hits:
            print(f"  {n}: {v:.3f} mm3")
            if "expected" not in n:
                bad.append(f"{title}: {n}")

    check("assembled, base vs PCB", [(n, _overlap(base, s)) for n, s in pcb.items()])
    check("assembled, lid vs PCB", [(n, _overlap(lid, s)) for n, s in pcb.items()])
    check("assembled, lid vs base", [("lid", _overlap(lid, base))])
    for dz in PATH_STEPS:
        check(f"PCB {dz} mm above seat vs base", [(n, _overlap(base, s.translate(cq.Vector(0, 0, dz)))) for n, s in pcb.items()])
    for dz in PATH_STEPS:
        moved = lid.translate(cq.Vector(0, 0, dz))
        contact = _overlap(moved, base)
        other = contact
        if flexing is not None and contact > MIN_VOLUME:
            other = _overlap(moved.cut(flexing.translate(cq.Vector(0, 0, dz))), base)
        pairs = [(n, _overlap(moved, s)) for n, s in pcb.items()] + [("base at flexing features (expected)", contact - other), ("base, other", other)]
        check(f"lid {dz} mm above seat vs PCB and base", pairs)
    if latches is not None:
        check(f"lid {latch_margin} mm above seat, latches vs base", [("latches", _overlap(latches.translate(cq.Vector(0, 0, latch_margin)), base))])
    return bad
