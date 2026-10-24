import json
from pathlib import Path

import pytest

from hwkit import lab as labmod
from hwkit import lessons, partsbox
from hwkit.kicad import manifest, setup
from hwkit.kicad.export import Project

SCH = '(kicad_sch\n\t(version 20250114)\n\t(paper "A4")\n\t(title_block\n\t\t(title "Old")\n\t\t(rev "1.0")\n\t)\n)\n'


def test_set_title_block_replace_and_add():
    text = setup.set_title_block(SCH, {"title": 'PRJ-0001 A "b"', "date": "2026-10-24"})
    assert '(title "PRJ-0001 A \\"b\\"")' in text
    assert '(date "2026-10-24")' in text
    assert '(rev "1.0")' in text
    with pytest.raises(ValueError):
        setup.set_title_block("(kicad_sch)", {"title": "x"})


def _project(tmp_path, stem="template"):
    (tmp_path / f"{stem}.kicad_pro").write_text(json.dumps({"meta": {"filename": f"{stem}.kicad_pro"}}))
    (tmp_path / f"{stem}.kicad_sch").write_text(SCH)
    (tmp_path / f"{stem}.kicad_pcb").write_text('(kicad_pcb (title_block (title "Old")))\n')
    return tmp_path / f"{stem}.kicad_pro"


def test_embed_models(tmp_path):
    import base64
    import hashlib
    import re

    import zstandard

    shapes = tmp_path / "parts.3dshapes"
    shapes.mkdir()
    data = bytes(range(256)) * 20
    (shapes / "R0603.step").write_bytes(data)
    fp = tmp_path / "R0603.kicad_mod"
    fp.write_text('(footprint "R0603"\n\t(model "${KIPRJMOD}/lib/parts.3dshapes/R0603.wrl"\n\t\t(offset (xyz 0 0 0))\n\t)\n)\n')
    assert setup.embed_models(fp, shapes)
    text = fp.read_text()
    assert '(model "kicad-embed://R0603.step"' in text
    encoded = re.search(r"\(data\n\|(.*?)\|\n", text, re.DOTALL).group(1)
    assert all(len(line.strip()) <= 76 for line in encoded.splitlines())
    assert zstandard.ZstdDecompressor().decompress(base64.b64decode("".join(encoded.split()))) == data
    assert f'(checksum "{hashlib.sha256(data).hexdigest()}")' in text
    assert not setup.embed_models(fp, shapes)


def test_rename(tmp_path):
    pro = _project(tmp_path)
    data = json.loads(pro.read_text())
    data["schematic"] = {"top_level_sheets": [{"filename": "template.kicad_sch", "name": "template", "uuid": "u"}]}
    data["sheets"] = [["u", "template"]]
    pro.write_text(json.dumps(data))
    pro = setup.rename(pro, "Quad Cell Amplifier")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Quad Cell Amplifier.kicad_pcb", "Quad Cell Amplifier.kicad_pro", "Quad Cell Amplifier.kicad_sch"]
    data = json.loads(pro.read_text())
    assert data["meta"]["filename"] == "Quad Cell Amplifier.kicad_pro"
    assert data["schematic"]["top_level_sheets"][0] == {"filename": "Quad Cell Amplifier.kicad_sch", "name": "Quad Cell Amplifier", "uuid": "u"}
    assert data["sheets"] == [["u", "Quad Cell Amplifier"]]


def test_link():
    from hwkit.distributors import _link

    assert _link("//mm.digikey.com/a.pdf") == "https://mm.digikey.com/a.pdf"
    assert _link("https://x/a.pdf") == "https://x/a.pdf"
    assert _link(None) == ""


def test_fab_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "rules_load", lambda *a: True)
    project = Project(_project(tmp_path))
    assert setup.check_fab_rules({}, project, tmp_path)[1]
    assert "pcbway-2layer-standard" in setup.processes()
    dru = setup.copy_fab_rules(project.pro, "pcbway-2layer-standard")
    assert setup.check_fab_rules({}, project, tmp_path) == (["process rules: pcbway-2layer-standard"], [])
    dru.write_text(dru.read_text() + '\n(rule "x" (constraint clearance (min 0.2mm)))\n')
    assert "differs" in setup.check_fab_rules({}, project, tmp_path)[0][0]
    monkeypatch.setattr(setup, "rules_load", lambda *a: False)
    assert "does not load" in setup.check_fab_rules({}, project, tmp_path)[1][0]
    with pytest.raises(ValueError):
        setup.copy_fab_rules(project.pro, "unknown")


LAB = labmod.load()


@pytest.mark.skipif(not Path(LAB["tools"]["kicad_cli"]).exists(), reason="no kicad-cli")
def test_library_rules_load_in_kicad(tmp_path):
    pcb = tmp_path / "b.kicad_pcb"
    pcb.write_text('(kicad_pcb (version 20240108) (generator "test"))\n')
    for process in setup.processes():
        assert setup.rules_load(LAB, pcb, setup.FAB_DIR / f"{process}.kicad_dru", tmp_path / process), process
    bad = tmp_path / "bad.kicad_dru"
    bad.write_text('(version 1)\n(rule "x" (constraint track_widthX (min 0.1mm)))\n')
    assert not setup.rules_load(LAB, pcb, bad, tmp_path / "bad")


def test_manifest(tmp_path):
    project = Project(_project(tmp_path))
    path = tmp_path / "manifest.json"
    assert manifest.check(path, project, 2)[1]
    manifest.write(path, project, 2)
    assert manifest.check(path, project, 2)[1] == []
    assert "boards" in manifest.check(path, project, 3)[1][0]
    project.pcb.write_text(project.pcb.read_text() + " ")
    assert "template.kicad_pcb" in manifest.check(path, project, 2)[1][0]


def test_lessons_limit(tmp_path):
    p = tmp_path / "l.md"
    p.write_text("# L\n\n" + "".join(f"- lesson {i}\n  more text\n" for i in range(lessons.MAX_ENTRIES)))
    assert lessons.check(p)[1] == []
    p.write_text(p.read_text() + "- one more\n")
    assert lessons.check(p)[1]


def test_toolkit_lessons_within_limit():
    from pathlib import Path

    assert lessons.check(Path(__file__).resolve().parents[1] / "lessons.md")[1] == []


def test_value_and_package():
    assert partsbox.value_number("4k7") == [4700.0]
    assert partsbox.value_number("100nF 50V X7R") == [pytest.approx(1e-7)]
    assert partsbox.value_number("10 kΩ 1% 0603") == [1e4, 1.0, 603.0]
    assert partsbox.package("Resistor_SMD:R_0603_1608Metric") == "0603"
    assert partsbox.package("SOT-23") is None


class FakeClient:
    def __init__(self, parts, storage):
        self._parts, self._storage, self.calls = parts, storage, []

    def parts(self):
        return self._parts

    def on_hand(self, pid):
        return self._storage[pid]

    def call(self, op, **params):
        self.calls.append((op, params))
        return {"project/all": [], "project/create": {"project/id": "p1"}}.get(op)


PARTS = [
    {"part/id": "a", "part/name": "RC0603FR-0710KL", "part/mpn": "RC0603FR-0710KL", "part/description": "10k 0603", "part/low-stock": {"report": 100}},
    {"part/id": "b", "part/name": "4k7 0603 1%", "part/description": ""},
    {"part/id": "c", "part/name": "4k7 0805", "part/description": ""},
]
FIELDS = {"manufacturer": "Manufacturer", "mpn": "MPN"}


def _row(refs, mpn, value, fp="Resistor_SMD:R_0603_1608Metric", qty="2"):
    return {"Refs": refs, "Qty": qty, "Value": value, "Footprint": fp, "Manufacturer": "Yageo", "MPN": mpn}


def test_stock_report():
    client = FakeClient(PARTS, {"a": 104, "b": 50, "c": 9})
    lines, notes, stock = partsbox.stock_report(client, [_row("R1,R2", "rc0603fr-0710kl", "10k"), _row("R3", "OTHER", "4k7"), _row("C1", "CAP", "1u")], FIELDS, 2)
    assert lines[0] == "R1 R2: rc0603fr-0710kl in stock: 104, need 4"
    assert notes == []
    assert stock == {"rc0603fr-0710kl": 104}
    client._storage["a"] = 103
    assert partsbox.stock_report(client, [_row("R1,R2", "RC0603FR-0710KL", "10k")], FIELDS, 2)[1] == ["R1 R2: RC0603FR-0710KL: stock after the build 99 < low-stock level 100"]
    assert lines[1].startswith("R3: OTHER not in stock; candidates")
    assert "4k7 0603 1%" in lines[2] and len(lines) == 4
    assert lines[3] == "C1: CAP not in stock"


def test_project_create_entries():
    client = FakeClient(PARTS, {})
    pid, created = partsbox.sync_project(client, "PRJ-0001 Demo v0.1", [_row("R1,R2", "RC0603FR-0710KL", "10k"), _row("R3", "OTHER", "4k7", qty="1")], FIELDS)
    assert (pid, created) == ("p1", True)
    op, params = client.calls[-1]
    assert op == "project/create"
    assert params["entries"][0] == {"entry/quantity": 2, "entry/designators": ["R1", "R2"], "entry/order": 0, "entry/part-id": "a"}
    assert params["entries"][1]["entry/name"] == "OTHER"


@pytest.mark.parametrize("category, ok", [("ok", True), ("status/ok", True), ("status/error", False)])
def test_client_status(monkeypatch, category, ok):
    import io

    body = json.dumps({"partsbox.status/category": category, "partsbox.status/message": "m", "data": [1]}).encode()
    monkeypatch.setattr(partsbox.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(body))
    client = partsbox.Client(key="k")
    if ok:
        assert client.call("part/all") == [1]
    else:
        with pytest.raises(RuntimeError):
            client.call("part/all")
