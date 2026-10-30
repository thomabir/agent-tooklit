import zipfile
from pathlib import Path

import cadquery as cq
import pytest

from hwkit import lab
from hwkit.bambu import INLAY_OBJECT_SETTINGS, checks, gcode, presets, project

SETTINGS = {"initial_layer_print_height": "0.3", "layer_height": "0.3", "different_settings_to_system": ["", "", "", ""]}


def test_indexed_mesh_shares_vertices():
    verts, tris = project.indexed_mesh(cq.Workplane().box(1, 1, 1).val())
    assert len(verts) == 8
    assert len(tris) == 12


@pytest.mark.parametrize("depth, layers", [(0.3, 1), (0.6, 2), (0.9, 3)])
def test_label_first_plate_settings(depth, layers):
    s = project.label_first_plate_settings(depth, SETTINGS, 2, 1)
    assert s["first_layer_print_sequence"] == "2 1"
    assert ("other_layers_print_sequence" in s) == (layers > 1)
    if layers > 1:
        assert s["other_layers_print_sequence"] == f"2 {layers} 2 1"


def test_write_project_round_trip(tmp_path):
    body = cq.Workplane().box(20, 20, 3).translate((0, 0, 1.5)).val()
    label = cq.Workplane().box(5, 5, 0.6).translate((0, 0, 0.3)).val()
    path = tmp_path / "p.3mf"
    objects = [
        {"name": "base", "parts": [("base", body, 1)], "center": (100, 128)},
        {"name": "lid", "parts": [("lid", body, 1), ("labels", label, 2)], "settings": INLAY_OBJECT_SETTINGS, "center": (150, 128)},
    ]
    project.write_project(path, objects, project.label_first_plate_settings(0.6, SETTINGS, 2, 1), SETTINGS)
    _, issues = checks.check_project(path, plate_first_layer="2 1")
    assert issues == []
    x0, x1, y0, y1 = checks.inlay_region(path)
    assert x0 < 150 < x1 and y0 < 128 < y1
    names = zipfile.ZipFile(path).namelist()
    assert "Metadata/project_settings.config" in names and "3D/Objects/object_2.model" in names


def test_missing_inlay_settings_reported(tmp_path):
    body = cq.Workplane().box(10, 10, 2).val()
    path = tmp_path / "p.3mf"
    project.write_project(path, [{"name": "lid", "parts": [("lid", body, 1), ("labels", body, 2)], "center": (128, 128)}], {}, SETTINGS)
    _, issues = checks.check_project(path)
    assert any("wall_generator" in i for i in issues)


@pytest.mark.skipif(not Path(lab.load()["tools"]["bambu_profiles"]).exists(), reason="Bambu Studio not installed")
def test_flat_machine_preset_has_printer_start_gcode():
    machine = presets.load_preset(lab.load(), "machine", lab.load()["printer"]["bambu_machine"])
    assert "M620" in machine["machine_start_gcode"]  # generic start G-code has no AMS load


def test_slow_label_layers_and_layer_ranges(tmp_path):
    overhang = {key: ["50", "50"] if key == "overhang_2_4_speed" else ["10", "10"] for key in project.OVERHANG_SPEED_KEYS}
    settings = SETTINGS | overhang | {"initial_layer_speed": ["35", "35"], "initial_layer_infill_speed": ["55", "55"], "print_extruder_variant": ["a", "b"], "machine_max_acceleration_x": ["20000"], "machine_max_acceleration_y": ["20000"]}
    slow, layer_range, layer_gcode = project.slow_label_layers(0.9, settings, speed=25, acceleration=800)
    assert slow["initial_layer_speed"] == ["25", "25"] and slow["initial_layer_infill_speed"] == ["25", "25"]
    assert slow["different_settings_to_system"][0] == "initial_layer_infill_speed;initial_layer_speed"
    assert layer_range[:2] == (0.0, 0.9) and layer_range[2]["outer_wall_speed"] == 25
    assert layer_range[2]["overhang_2_4_speed"] == 25 and layer_range[2]["overhang_4_4_speed"] == 10
    assert layer_gcode == [(0.3, "M201 X800 Y800"), (1.2, "M201 X20000 Y20000")]
    body = cq.Workplane().box(10, 10, 2).translate((0, 0, 1)).val()
    path = tmp_path / "p.3mf"
    project.write_project(path, [{"name": "lid", "parts": [("lid", body, 1)], "center": (128, 128), "layer_ranges": [layer_range]}], {}, slow, layer_gcode=layer_gcode)
    xml = zipfile.ZipFile(path).read("Metadata/layer_config_ranges.xml").decode()
    assert '<object id="1">' in xml and 'max_z="0.9"' in xml and '<option opt_key="outer_wall_speed">25,25</option>' in xml and '<option opt_key="layer_height">0.3</option>' in xml
    gx = zipfile.ZipFile(path).read("Metadata/custom_gcode_per_layer.xml").decode()
    assert 'top_z="0.3" type="4"' in gx and 'extra="M201 X800 Y800"' in gx


def test_max_feed_rates(tmp_path):
    g = tmp_path / "g.gcode"
    g.write_text("M201 X20000 Y20000\n; CHANGE_LAYER\nM201 X1000 Y1000\n; FEATURE: Outer wall\nG1 F1800\nG1 X1 Y0 E.1\nG1 X5 Y5 F30000\n; FEATURE: Prime tower\nG1 X2 E.1 F6000\n; CHANGE_LAYER\nM201 X20000 Y20000\n; FEATURE: Inner wall\nG1 X3 E.1 F3600\n")
    assert gcode.max_feed_rates(g, 2) == ([30.0, 60.0], [1000.0, 20000.0])
