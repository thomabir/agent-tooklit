"""Blender script: exploded views of STL parts and a KiCad GLB. Run by hwkit.render.exploded(); config JSON path after "--".

Config keys: out_dir, name, parts [{stl, rgba, z}], glb {path, matrix (4x4, rows)}, views {name: [dx, dy, dz]}, resolution [w, h], samples.
Output: <out_dir>/<name>-<view>.png and <out_dir>/<name>.png (views side by side).
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

cfg = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
OUT = Path(cfg["out_dir"])
RES = cfg.get("resolution", [1400, 1100])


def material(name, rgba):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.55
    return m


def import_stl(part):
    bpy.ops.wm.stl_import(filepath=part["stl"])
    ob = bpy.context.selected_objects[0]
    ob.data.materials.append(material(Path(part["stl"]).stem, part["rgba"]))
    ob.location.z = part.get("z", 0.0)
    bpy.ops.object.shade_auto_smooth(angle=math.radians(30))
    return [ob]


def import_glb(glb):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=glb["path"])
    new = [ob for ob in bpy.context.scene.objects if ob not in before]
    root = bpy.data.objects.new("glb", None)
    bpy.context.scene.collection.objects.link(root)
    for ob in new:
        if ob.parent is None:
            ob.parent = root
    root.matrix_world = Matrix(glb["matrix"])
    return [ob for ob in new if ob.type == "MESH"]


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = cfg.get("samples", 64)
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.view_settings.view_transform = "Standard"
    scene.render.use_freestyle = True
    scene.render.line_thickness = 0.8
    style = bpy.data.linestyles.new("edges")  # a lineset without linestyle fails in background mode
    style.color = (0.1, 0.1, 0.12)
    for layer in scene.view_layers:
        if len(layer.freestyle_settings.linesets) == 0:
            layer.freestyle_settings.linesets.new("edges")
        for ls in layer.freestyle_settings.linesets:
            ls.linestyle = style
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.92, 0.93, 0.95, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    scene.world = world
    for direction, energy in ((Vector((-0.5, -1.0, 1.5)), 3.0), (Vector((1.0, 0.8, 0.6)), 1.2), (Vector((0.3, -0.5, -1.0)), 0.8)):
        light = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
        light.data.energy = energy
        light.data.angle = math.radians(10)
        light.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
        scene.collection.objects.link(light)


def camera_for(objects, direction):
    bpy.context.view_layer.update()
    pts = [ob.matrix_world @ Vector(c) for ob in objects for c in ob.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.location = (lo + hi) / 2 + direction.normalized() * 300
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = 1000
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    c = [inv @ Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    w = max(v.x for v in c) - min(v.x for v in c)
    h = max(v.y for v in c) - min(v.y for v in c)
    cam.data.ortho_scale = 1.08 * max(w, h * RES[0] / RES[1])
    return cam


def contact_sheet(paths, out_path):
    import numpy as np

    images = [bpy.data.images.load(str(p)) for p in paths]
    w, h = images[0].size
    sheet = np.concatenate([np.array(i.pixels[:], dtype=np.float32).reshape(h, w, 4) for i in images], axis=1)
    out = bpy.data.images.new("sheet", width=w * len(images), height=h, alpha=True)
    out.pixels = sheet.ravel()
    out.filepath_raw = str(out_path)
    out.file_format = "PNG"
    out.save()


bpy.ops.wm.read_factory_settings(use_empty=True)
setup_scene()
objects = [ob for part in cfg["parts"] for ob in import_stl(part)]
if cfg.get("glb"):
    objects += import_glb(cfg["glb"])
paths = []
for view, d in cfg["views"].items():
    bpy.context.scene.camera = camera_for(objects, Vector(d))
    path = OUT / f"{cfg['name']}-{view}.png"
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    paths.append(path)
contact_sheet(paths, OUT / f"{cfg['name']}.png")
