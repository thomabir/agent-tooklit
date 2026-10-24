from hwkit import readme
from hwkit.kicad import report, sexp
from hwkit.prices import Prices, write


def _template():
    out = ["# PRJ-0001 Demo", "<!-- BEGIN generated: bom -->", "<!-- END generated: bom -->"]
    for h2, h3 in readme.SECTIONS:
        if h3 is None:
            out += [f"## {h2}", "<!-- guidance -->", "TODO"]
        else:
            out += [f"### {h3}", "<!-- guidance -->", "TODO"]
    return "\n".join(out) + "\n"


def test_template_sections_all_todo():
    lines, issues = readme.check(_template())
    assert issues == []
    assert any(line.startswith("NOTE: README: TODO") for line in lines)
    _, issues = readme.check(_template(), release=True)
    assert len(issues) == 1 and "TODO" in issues[0]


def test_missing_empty_and_na_sections():
    text = _template().replace("### Safety\n<!-- guidance -->\nTODO", "### Safety\n<!-- guidance -->\nN/A: no voltage above 5 V.")
    text = text.replace("### Case\n<!-- guidance -->\nTODO\n", "")
    text = text.replace("## Licence\n<!-- guidance -->\nTODO", "## Licence\n<!-- only a comment -->")
    lines, issues = readme.check(text)
    assert "  N/A: Systems engineering / Safety (no voltage above 5 V.)" in lines
    assert any("'Build / Case' is missing" in i for i in issues)
    assert any("'Licence' is empty" in i for i in issues)


def test_title_must_match():
    _, issues = readme.check(_template(), expected_title="PRJ-0001 Other")
    assert any("title" in i for i in issues)


def test_update_generated_block():
    text, missing = readme.update(_template(), {"bom": "| a |", "titleblock": "x"})
    assert missing == ["titleblock"]
    assert readme.blocks(text) == {"bom": "| a |\n"}
    assert readme.update(text, {"bom": "| a |"})[0] == text


def test_set_title():
    assert readme.set_title("x\n# Old\n# Second\n", "PRJ-0002 New") == "x\n# PRJ-0002 New\n# Second\n"


FIELDS = {"manufacturer": "Manufacturer", "mpn": "MPN", "datasheet": "Datasheet", "digikey": "DigiKey", "mouser": "Mouser", "notes": "Notes"}


def _bom_row(**kw):
    return {"Refs": "R1,R2", "Qty": "2", "DNP": "", "Value": "10k", "Footprint": "R_0603", "Manufacturer": "Yageo", "MPN": "RC0603", "Datasheet": "https://ds", "DigiKey": "https://www.digikey.ch/x", "Mouser": "", "Notes": "a|b"} | kw


PCB = sexp.parse("""(kicad_pcb (general (thickness 1.6))
  (title_block (title "PRJ-0001 Demo") (date "2026-10-24") (rev "0.1") (company "A"))
  (gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts"))
  (footprint "R" (attr smd)) (footprint "R" (attr smd)) (footprint "J" (attr through_hole))
  (footprint "H" (attr exclude_from_bom)) (footprint "R" (attr smd dnp)))""")


def test_bom_block_prices_and_count(tmp_path):
    path = tmp_path / "prices.csv"
    rows = [{"manufacturer": "Yageo", "mpn": "RC0603", "distributor": "digikey", "part_number": "X-ND", "quantity": q, "unit_price": p, "currency": "CHF", "date": "2026-10-24"} for q, p in ((1, 0.1), (10, 0.02))]
    write(path, rows)
    block = report.bom_block([_bom_row(), _bom_row(Refs="R3", MPN="NONE", DNP="DNP")], FIELDS, Prices(path), 5, PCB)
    assert "| R1 R2 | 2 | 10k | Yageo | [RC0603](https://ds) | [DigiKey](https://www.digikey.ch/x) | 0.020 | a\\|b |" in block
    assert "Price per board: 0.20 CHF at 1 board, 0.04 CHF at 5 boards. Prices: digikey, 2026-10-24." in block
    assert "Parts per board: 3 (SMD 2, THT 1)." in block
    assert "R3" not in block


def test_bom_block_without_prices():
    block = report.bom_block([_bom_row()], FIELDS, Prices(""), 2, PCB)
    assert "No price: R1 R2." in block


def test_version_block():
    block = report.version_block(PCB, "Demo Board", "pcb")
    assert "| 0.1 | 2026-10-24 | [Schematic](pcb/docs/Demo%20Board-schematic.pdf) " in block
    assert "[Gerbers](pcb/manufacturing/Demo%20Board-v0.1-gerbers.zip)" in block
