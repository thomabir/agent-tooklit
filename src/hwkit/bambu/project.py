"""Bambu Studio project 3MF writer. Format: see skills/bambu-print-prep/SKILL.md."""

import json
import math
import uuid
import zipfile
from xml.sax.saxutils import escape

APPLICATION = "BambuStudio-02.07.01.62"  # must start with "BambuStudio-"; an old version selects compatibility code paths
CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
REL_TYPE = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
HEAD = f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="{PROD}" requiredextensions="p">'


def indexed_mesh(shape, tolerance=0.01, angular_tolerance=0.1):
    """(vertices, triangles) with one vertex per position. tessellate() gives each face its own vertices; see lessons.md (L03)."""
    verts, tris = shape.tessellate(tolerance, angular_tolerance)
    index, unique, remap = {}, [], []
    for v in verts:
        key = (round(v.x, 4), round(v.y, 4), round(v.z, 4))
        if key not in index:
            index[key] = len(unique)
            unique.append(key)
        remap.append(index[key])
    faces = [(remap[a], remap[b], remap[c]) for a, b, c in tris]
    return unique, [f for f in faces if len(set(f)) == 3]


def label_first_plate_settings(label_depth, project_settings, label_filament, body_filament):
    """Plate settings: on each layer with labels, the label filament prints first. See lessons.md (L08)."""
    first = float(project_settings["initial_layer_print_height"])
    other = float(project_settings["layer_height"])
    layers = 1 + max(0, math.ceil((label_depth - first) / other - 1e-9))
    order = f"{label_filament} {body_filament}"
    settings = {"first_layer_print_sequence": order}  # space-separated; "2,1" has no effect
    if layers > 1:
        settings |= {"other_layers_print_sequence": f"2 {layers} {order}", "other_layers_print_sequence_nums": "1"}  # start layer, end layer, order
    return settings


def write_project(path, objects, plate_settings, project_settings):
    """Write a Bambu Studio project 3MF with all objects on plate 1.

    objects: list of {"name", "parts": [(part name, cq.Shape in print orientation, filament number)], "settings": {key: value}, "center": (x, y) on the plate}.
    project_settings: dict from a template made by hwkit.bambu.presets.make_template().
    """

    def uid(tag):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path.name}/{tag}"))

    files = {}
    root = [HEAD, f' <metadata name="Application">{APPLICATION}</metadata>', ' <metadata name="BambuStudio:3mfVersion">1</metadata>', " <resources>"]
    build = [f' <build p:UUID="{uid("build")}">']
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    n_parts = sum(len(o["parts"]) for o in objects)
    mesh_id = 0
    for k, obj in enumerate(objects, start=1):
        group_id = n_parts + k
        model_path = f"3D/Objects/object_{k}.model"
        mesh = [HEAD, ' <metadata name="BambuStudio:3mfVersion">1</metadata>', " <resources>"]
        lo, hi = [math.inf] * 3, [-math.inf] * 3
        part_ids = []
        for name, shape, _ in obj["parts"]:
            mesh_id += 1
            part_ids.append(mesh_id)
            verts, tris = indexed_mesh(shape)
            for v in verts:
                lo = [min(a, b) for a, b in zip(lo, v)]
                hi = [max(a, b) for a, b in zip(hi, v)]
            mesh.append(f'  <object id="{mesh_id}" p:UUID="{uid(obj["name"] + "/" + name)}" type="model"><mesh><vertices>')
            mesh.extend(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in verts)
            mesh.append("</vertices><triangles>")
            mesh.extend(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris)
            mesh.append("</triangles></mesh></object>")
        mesh.append(" </resources>\n <build/>\n</model>")
        files[model_path] = "\n".join(mesh)

        root.append(f'  <object id="{group_id}" p:UUID="{uid(obj["name"])}" type="model"><components>')
        root.extend(f'   <component p:path="/{model_path}" objectid="{i}" p:UUID="{uid(obj["name"] + f"/component{i}")}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' for i in part_ids)
        root.append("  </components></object>")
        dx = obj["center"][0] - (lo[0] + hi[0]) / 2
        dy = obj["center"][1] - (lo[1] + hi[1]) / 2
        build.append(f'  <item objectid="{group_id}" p:UUID="{uid(obj["name"] + "/item")}" transform="1 0 0 0 1 0 0 0 1 {dx:.4f} {dy:.4f} {-lo[2]:.4f}" printable="1"/>')

        cfg += [f'  <object id="{group_id}">', f'    <metadata key="name" value="{escape(obj["name"])}"/>', '    <metadata key="extruder" value="1"/>']
        cfg.extend(f'    <metadata key="{key}" value="{escape(str(v))}"/>' for key, v in obj.get("settings", {}).items())
        for i, (name, _, filament) in zip(part_ids, obj["parts"]):
            cfg += [f'    <part id="{i}" subtype="normal_part">', f'      <metadata key="name" value="{escape(name)}"/>', '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>', f'      <metadata key="extruder" value="{filament}"/>', "    </part>"]
        cfg.append("  </object>")
    root.append(" </resources>")
    build.append(" </build>\n</model>")
    cfg += ["  <plate>", '    <metadata key="plater_id" value="1"/>']
    cfg.extend(f'    <metadata key="{key}" value="{escape(str(v))}"/>' for key, v in plate_settings.items())
    for k in range(1, len(objects) + 1):
        cfg += ["    <model_instance>", f'      <metadata key="object_id" value="{n_parts + k}"/>', '      <metadata key="instance_id" value="0"/>', "    </model_instance>"]
    cfg += ["  </plate>", "</config>"]

    content_types = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/><Default Extension="config" ContentType="text/xml"/></Types>'
    rels = f'<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="{REL_TYPE}"/></Relationships>'
    model_rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    model_rels += "".join(f'<Relationship Target="/{m}" Id="rel{k}" Type="{REL_TYPE}"/>' for k, m in enumerate(files, start=1)) + "</Relationships>"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", "\n".join(root + build))
        z.writestr("3D/_rels/3dmodel.model.rels", model_rels)
        for name, text in files.items():
            z.writestr(name, text)
        z.writestr("Metadata/model_settings.config", "\n".join(cfg))
        z.writestr("Metadata/project_settings.config", json.dumps(project_settings, indent=4) + "\n")
