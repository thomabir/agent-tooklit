"""Checks of a Bambu project 3MF and of the settings in a G-code header."""

import json
import re
import xml.etree.ElementTree as ET
import zipfile

from . import INLAY_OBJECT_SETTINGS

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02", "p": "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"}


def _meta(el):
    return {m.get("key"): m.get("value") for m in el.findall("metadata") if m.get("key")}


def read_objects(z):
    """{object id: {"meta": {...}, "parts": [{...}]}} from Metadata/model_settings.config."""
    root = ET.fromstring(z.read("Metadata/model_settings.config"))
    return {o.get("id"): {"meta": _meta(o), "parts": [_meta(p) for p in o.iter("part")]} for o in root.iter("object")}


def inlay_objects(objects):
    """Ids of objects with a part on a filament other than 1."""
    return [oid for oid, o in objects.items() if any(p.get("extruder", o["meta"].get("extruder", "1")) != "1" for p in o["parts"])]


def check_project(path, plate_first_layer=None):
    """(report lines, issues). Issues: inlay object without INLAY_OBJECT_SETTINGS, no inlay object, wrong first_layer_print_sequence."""
    z = zipfile.ZipFile(path)
    project = json.loads(z.read("Metadata/project_settings.config"))
    objects = read_objects(z)
    inlay = inlay_objects(objects)
    lines = [
        f"printer: {project.get('printer_settings_id')}",
        f"process: {project.get('print_settings_id')}",
        f"filaments: {project.get('filament_settings_id')}, colours {project.get('filament_colour')}",
        f"different_settings_to_system: {project.get('different_settings_to_system')}",
    ]
    issues = []
    for oid, o in objects.items():
        settings = {k: v for k, v in o["meta"].items() if k not in ("name", "extruder")}
        lines.append(f"object {o['meta'].get('name')}: {settings}")
        lines += [f"  part {p.get('name')}: filament {p.get('extruder', o['meta'].get('extruder', '1'))}" for p in o["parts"]]
        if oid in inlay:
            issues += [f"object {o['meta'].get('name')}: per-object setting {k} = {v} missing (found {o['meta'].get(k)})" for k, v in INLAY_OBJECT_SETTINGS.items() if o["meta"].get(k) != v]
    if not inlay:
        issues.append("no part on a filament other than 1")
    plate = _meta(ET.fromstring(z.read("Metadata/model_settings.config")).find("plate"))
    lines.append(f"plate: { {k: v for k, v in plate.items() if 'sequence' in k} }")
    if plate_first_layer is not None and plate.get("first_layer_print_sequence") != plate_first_layer:
        issues.append(f"plate first_layer_print_sequence is {plate.get('first_layer_print_sequence')}, expected {plate_first_layer}")
    return lines, issues


def object_region(path, object_id, margin=3.0):
    """Build-plate bounding box (x0, x1, y0, y1) of an object, with a margin in mm."""
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("3D/3dmodel.model"))
    obj = root.find(f"m:resources/m:object[@id='{object_id}']", NS)
    t = [float(v) for v in root.find(f"m:build/m:item[@objectid='{object_id}']", NS).get("transform").split()]
    xs, ys = [], []
    for comp in obj.find("m:components", NS):
        mesh_obj = ET.fromstring(z.read(comp.get(f"{{{NS['p']}}}path").lstrip("/"))).find(f"m:resources/m:object[@id='{comp.get('objectid')}']", NS)
        for v in mesh_obj.iter(f"{{{NS['m']}}}vertex"):
            xs.append(float(v.get("x")) + t[9])
            ys.append(float(v.get("y")) + t[10])
    return min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin


def inlay_region(path):
    return object_region(path, inlay_objects(read_objects(zipfile.ZipFile(path)))[0])


def _header(gcode):
    header = {}
    for line in open(gcode):
        m = re.match(r"^; (\w+) = (.*)$", line)
        if m:
            header.setdefault(m.group(1), m.group(2).strip())
    return header


def check_gcode_settings(gcode, project_path, extra_keys=()):
    """(report lines, issues): G-code header values of the keys in different_settings_to_system and extra_keys against the project values."""
    project = json.loads(zipfile.ZipFile(project_path).read("Metadata/project_settings.config"))
    keys = {k for entry in project.get("different_settings_to_system", []) for k in entry.split(";") if k} | set(extra_keys)
    header = _header(gcode)
    lines, issues = [], []
    for key in sorted(keys):
        want = project.get(key)
        want = ",".join(want) if isinstance(want, list) else str(want)
        used = header.get(key)
        lines.append(f"G-code {key}: {used} (project {want})")
        if used != want:
            issues.append(f"G-code {key} is {used}, project has {want}")
    return lines, issues
