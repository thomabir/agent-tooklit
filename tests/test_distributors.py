from hwkit import distributors
from hwkit.kicad import fields, sexp

SCH = """(kicad_sch
	(version 20250114)
	(lib_symbols
		(symbol "Device:R"
			(property "Reference" "R"
				(at 0 0 0)
			)
		)
	)
	(symbol
		(lib_id "Device:R")
		(at 10 10 0)
		(property "Reference" "R1"
			(at 10 8 0)
		)
		(property "Manufacturer" "Yageo"
			(at 10 10 0)
			(hide yes)
		)
		(property "MPN" "RC0603 \\"x\\" (1k)"
			(at 10 12 0)
			(hide yes)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "DigiKey PN" ""
			(at 10 14 0)
			(hide yes)
		)
	)
	(symbol
		(lib_id "Device:R")
		(property "Reference" "R2"
			(at 0 0 0)
		)
		(property "MPN" "OTHER"
			(at 0 0 0)
		)
	)
)
"""


def test_symbols_skip_lib_symbols():
    assert [p["Reference"] for p in fields.placed(SCH)] == ["R1", "R2"]
    assert fields.placed(SCH)[0]["MPN"] == 'RC0603 "x" (1k)'


def test_set_fields_replace_and_insert():
    def match(p):
        return p.get("Manufacturer") == "Yageo"

    text, n, conflicts = fields.set_fields(SCH, match, {"DigiKey PN": "311-1KCT-ND", "DigiKey": 'https://www.digikey.ch/a"b'}, after="MPN")
    assert (n, conflicts) == (2, [])
    r1, r2 = fields.placed(text)
    assert r1["DigiKey PN"] == "311-1KCT-ND"
    assert r1["DigiKey"] == 'https://www.digikey.ch/a"b'
    assert "DigiKey" not in r2
    sexp.parse(text)
    new = text[text.index('(property "DigiKey" ') :]
    assert new.splitlines()[1].strip() == "(at 10 12 0)"  # copy of the MPN field: same position, hidden
    assert fields.set_fields(text, match, {"DigiKey PN": "311-1KCT-ND"}, after="MPN") == (text, 0, [])


def test_set_fields_conflict_and_replace():
    def match(p):
        return p.get("Manufacturer") == "Yageo"

    text, _, _ = fields.set_fields(SCH, match, {"DigiKey PN": "A-ND"}, after="MPN")
    assert fields.set_fields(text, match, {"DigiKey PN": "B-ND"}, after="MPN") == (text, 0, [("DigiKey PN", "A-ND", "B-ND")])
    text, n, conflicts = fields.set_fields(text, match, {"DigiKey PN": "B-ND"}, after="MPN", replace=True)
    assert (n, conflicts, fields.placed(text)[0]["DigiKey PN"]) == (1, [], "B-ND")


def _product(mpn="RC0603", mfr="YAGEO", variations=None):
    return {
        "ManufacturerProductNumber": mpn,
        "Manufacturer": {"Name": mfr},
        "ProductUrl": "https://www.digikey.ch/en/products/detail/x/1",
        "ProductStatus": {"Status": "Active"},
        "ProductVariations": variations
        or [
            {"DigiKeyProductNumber": "311-TR-ND", "PackageType": {"Name": "Tape & Reel (TR)"}, "MinimumOrderQuantity": 5000, "QuantityAvailableforPackageType": 50000, "StandardPricing": []},
            {"DigiKeyProductNumber": "311-CT-ND", "PackageType": {"Name": "Cut Tape (CT)"}, "MinimumOrderQuantity": 1, "QuantityAvailableforPackageType": 100, "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 0.1}, {"BreakQuantity": 10, "UnitPrice": 0.05}]},
            {"DigiKeyProductNumber": "311-DKR-ND", "PackageType": {"Name": "Digi-Reel®"}, "MinimumOrderQuantity": 1, "QuantityAvailableforPackageType": 50000, "StandardPricing": []},
        ],
    }


def _digikey(products):
    d = distributors.DigiKey("id", "secret", "CH", "en", "CHF")
    d._products = lambda mpn: products
    return d


def test_digikey_lookup_cut_tape():
    offer, note = _digikey([_product(), _product(mpn="RC0603-X")]).lookup("Yageo", "rc0603")
    assert (offer.part_number, offer.unit_price, offer.package, note) == ("311-CT-ND", 0.1, "Cut Tape (CT)", "Active")


def test_digikey_lookup_no_match_and_ambiguous():
    assert _digikey([_product(mfr="Vishay")]).lookup("Yageo", "RC0603") == (None, "no exact MPN match")
    offer, note = _digikey([_product(mfr="Amphenol ICC"), _product(mfr="Amphenol CS")]).lookup("Amphenol", "RC0603")
    assert offer is None and note.startswith("several products")
    reel = [{"DigiKeyProductNumber": "R", "PackageType": {"Name": "Tape & Reel (TR)"}}]
    assert _digikey([_product(variations=reel)]).lookup("Yageo", "RC0603") == (None, "only full-reel packaging")


def test_credentials_env_overrides_file(tmp_path, monkeypatch):
    f = tmp_path / "c.toml"
    f.write_text('[digikey]\nclient_id = "file"\nclient_secret = "s"\n')
    monkeypatch.setenv("HWKIT_CREDENTIALS", str(f))
    monkeypatch.setenv("DIGIKEY_CLIENT_ID", "env")
    monkeypatch.delenv("MOUSER_API_KEY", raising=False)
    c = distributors.load_credentials()
    assert c["digikey"] == {"client_id": "env", "client_secret": "s"}
    assert "mouser" not in c
