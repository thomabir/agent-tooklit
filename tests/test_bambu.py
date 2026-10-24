import zipfile
from pathlib import Path

import cadquery as cq
import pytest

from hwkit import lab
from hwkit.bambu import INLAY_OBJECT_SETTINGS, checks, presets, project

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
