from hwkit.kicad import checks, sexp
from hwkit.kicad.export import write_order_files

FIELDS = {"manufacturer": "Manufacturer", "mpn": "MPN", "digikey": "DigiKey", "digikey_pn": "DigiKey PN", "mouser": "Mouser"}


def _board(outline, hole_at="13 13", zone=True, silk="${TITLE} v${REVISION}"):
    zone_txt = '(zone (net 1) (net_name "GND") (layers "F.Cu" "B.Cu") (filled_polygon (layer "F.Cu") (pts (xy 0 0))))' if zone else ""
    return sexp.parse(f"""(kicad_pcb (version 20250101)
      (title_block (title "Demo") (date "2026-10-22") (rev "1.0") (company "A. Author"))
      (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
      (net 0 "") (net 1 "GND")
      (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (at {hole_at}) (property "Reference" "H1" (at 0 0)))
      {outline}
      {zone_txt}
      (segment (start 1 1) (end 2 2) (width 0.25) (layer "F.Cu") (net 1))
      (gr_text "{silk}" (at 20 20) (layer "F.SilkS")))""")


ROUNDED = """
  (gr_line (start 12 10) (end 48 10) (layer "Edge.Cuts"))
  (gr_arc (start 48 10) (mid 49.4142 10.5858) (end 50 12) (layer "Edge.Cuts"))
  (gr_line (start 50 12) (end 50 38) (layer "Edge.Cuts"))
  (gr_arc (start 50 38) (mid 49.4142 39.4142) (end 48 40) (layer "Edge.Cuts"))
  (gr_line (start 48 40) (end 12 40) (layer "Edge.Cuts"))
  (gr_arc (start 12 40) (mid 10.5858 39.4142) (end 10 38) (layer "Edge.Cuts"))
  (gr_line (start 10 38) (end 10 12) (layer "Edge.Cuts"))
  (gr_arc (start 10 12) (mid 10.5858 10.5858) (end 12 10) (layer "Edge.Cuts"))"""


def test_sexp_strings_and_nesting():
    n = sexp.parse('(a "x y" (b 1 2) (c "q\\"z"))')
    assert n[1] == "x y"
    assert sexp.xy(n, "b") == (1.0, 2.0)
    assert sexp.value(n, "c") == 'q"z'


def test_board_rounded_outline_passes():
    lines, issues = checks.check_board(_board(ROUNDED), ["GND"], 1.0, 30.0)
    assert issues == []
    assert any("40.000 mm × 30.000 mm" in line for line in lines)
    assert any("NOTE: 1 track segment" in line for line in lines)


def test_board_sharp_rect_hole_off_grid_no_zone():
    rect = '(gr_rect (start 10 10) (end 50 40) (layer "Edge.Cuts"))'
    _, issues = checks.check_board(_board(rect, hole_at="13.5 13", zone=False), ["GND"], 1.0, 30.0)
    assert any("without corner radius" in i for i in issues)
    assert any("x = 3.500 mm" in i for i in issues)
    assert any("no zone on a ground net" in i for i in issues)


def test_board_sharp_line_corner():
    square = "".join(f'(gr_line (start {a}) (end {b}) (layer "Edge.Cuts"))' for a, b in [("0 0", "10 0"), ("10 0", "10 10"), ("10 10", "0 10"), ("0 10", "0 0")])
    _, issues = checks.check_board(_board(square, hole_at="3 3"), ["GND"], 1.0, 30.0)
    assert sum("sharp board corner" in i for i in issues) == 4


def test_silkscreen_note():
    lines, _ = checks.check_board(_board(ROUNDED, silk="hello"), ["GND"], 1.0, 30.0)
    assert any(line.startswith("NOTE: silkscreen") for line in lines)


def test_title_blocks():
    good = {"title": "Demo", "rev": "1.0", "date": "2026-10-22", "company": "A. Author"}
    assert checks.check_title_blocks({"a": good, "b": dict(good)}, "A. Author")[1] == []
    bad = dict(good, rev="v1", date="22.10.2026")
    issues = checks.check_title_blocks({"a": good, "b": bad}, "A. Author")[1]
    assert any("Major.Minor" in i for i in issues)
    assert any("YYYY-MM-DD" in i for i in issues)
    assert any("differs" in i for i in issues)


def _row(**kw):
    r = {"Refs": "R1", "Qty": "2", "DNP": "", "Manufacturer": "Yageo", "MPN": "RC0603", "DigiKey": "https://www.digikey.com/x", "DigiKey PN": "311-1.00KCRCT-ND", "Mouser": "https://www.mouser.com/x"}
    return r | kw


def test_bom_fields():
    assert checks.check_bom([_row()], FIELDS)[1] == []
    issues = checks.check_bom([_row(MPN="", Mouser="www.mouser.com/x")], FIELDS)[1]
    assert len(issues) == 2


def test_order_files(tmp_path):
    dk, mo = write_order_files([_row(), _row(Refs="R2", DNP="DNP")], FIELDS, 5, tmp_path)
    text = mo.read_text().splitlines()
    assert len(text) == 2
    assert text[1].startswith("R1,10,Yageo,RC0603")
    assert dk.read_text().splitlines() == ["Digi-Key Part Number,Quantity,Customer Reference", "311-1.00KCRCT-ND,10,R1"]


FIELDS_QTY = FIELDS | {"order_qty": "Order Qty"}


def test_order_qty_field(tmp_path):
    rows = [_row(**{"Order Qty": ""}), _row(Refs="R2", MPN="B", **{"Order Qty": "0"}), _row(Refs="R3", MPN="C", **{"Order Qty": "100"}), _row(Refs="R4", MPN="D", **{"Order Qty": "3"})]
    _, mo = write_order_files(rows, FIELDS_QTY, 5, tmp_path)
    text = mo.read_text().splitlines()
    assert [line.split(",")[:2] for line in text[1:]] == [["R1", "10"], ["R3", "100"], ["R4", "10"]]


def test_order_files_merge_same_part(tmp_path):
    rows = [_row(Refs="J1", Qty="1", MPN="112659"), _row(Refs="J2", Qty="1", MPN="112659"), _row(Refs="J3", DNP="DNP", MPN="112659")]
    dk, mo = write_order_files(rows, FIELDS, 2, tmp_path)
    assert mo.read_text().splitlines()[1].startswith('"J1,J2",4,Yageo,112659')
    assert dk.read_text().splitlines()[1] == "311-1.00KCRCT-ND,4,J1 J2"


def test_order_files_merge_conflicting_order_qty(tmp_path):
    rows = [_row(Refs="R1", **{"Order Qty": "0"}), _row(Refs="R2", **{"Order Qty": "100"})]
    try:
        write_order_files(rows, FIELDS_QTY, 2, tmp_path)
    except ValueError as e:
        assert "differs" in str(e)
    else:
        raise AssertionError("no ValueError")


def test_bom_order_qty_optional():
    assert checks.check_bom([_row()], FIELDS_QTY)[1] == []
    assert checks.check_bom([_row(**{"Order Qty": "50"})], FIELDS_QTY)[1] == []
    assert len(checks.check_bom([_row(**{"Order Qty": "-1"})], FIELDS_QTY)[1]) == 1


def test_order_file_digikey_pn_missing(tmp_path):
    try:
        write_order_files([_row(**{"DigiKey PN": ""})], FIELDS, 5, tmp_path)
    except ValueError as e:
        assert "DigiKey PN" in str(e)
    else:
        raise AssertionError("no ValueError")


def test_bom_digikey_pn():
    assert len(checks.check_bom([_row(**{"DigiKey PN": ""})], FIELDS)[1]) == 1
    assert len(checks.check_bom([_row(**{"DigiKey PN": "311-1.00KCRCT"})], FIELDS)[1]) == 1
