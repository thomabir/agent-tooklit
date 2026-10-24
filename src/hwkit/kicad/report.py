"""README blocks from a KiCad project: title block data, board size, BOM with prices, part count."""

from ..readme import table
from . import sexp
from .checks import Outline, title_block
from .export import merge_by_part


def board_summary(pcb_root, copper_layers):
    tb = title_block(pcb_root)
    x0, y0, x1, y1 = Outline(pcb_root).bbox()
    thickness = sexp.value(sexp.child(pcb_root, "general") or ["general"], "thickness", "")
    header = ["Version", "Date", "Board size", "Thickness", "Copper layers"]
    row = [tb["rev"], tb["date"], f"{x1 - x0:.1f} mm × {y1 - y0:.1f} mm", f"{float(thickness):.2f} mm" if thickness else "", str(len(copper_layers))]
    return table(header, [row])


def _attrs(fp):
    a = sexp.child(fp, "attr")
    tokens = set(a[1:]) if a else set()
    if sexp.value(fp, "dnp") == "yes":
        tokens.add("dnp")
    if sexp.value(fp, "exclude_from_bom") == "yes":
        tokens.add("exclude_from_bom")
    return tokens


def part_count(pcb_root):
    """(total, SMD, THT, other) of the footprints that are in the BOM and not DNP."""
    smd = tht = other = 0
    for fp in sexp.children(pcb_root, "footprint"):
        a = _attrs(fp)
        if a & {"dnp", "exclude_from_bom", "board_only"}:
            continue
        if "smd" in a:
            smd += 1
        elif "through_hole" in a:
            tht += 1
        else:
            other += 1
    return smd + tht + other, smd, tht, other


def _link(text, url):
    return f"[{text}]({url})" if url and url.strip() not in ("", "~") else text


def bom_block(rows, fields, prices, boards, pcb_root):
    """BOM table (DNP lines left out, same parts merged), price per board at 1 and at boards boards, part count."""
    rows = merge_by_part(rows, fields)
    f = fields
    out_rows, total_1, total_n, missing, sources, currencies = [], 0.0, 0.0, [], set(), set()
    for r in rows:
        qty = int(r["Qty"])
        p1 = prices.unit_price(r[f["manufacturer"]], r[f["mpn"]], qty)
        pn = prices.unit_price(r[f["manufacturer"]], r[f["mpn"]], qty * boards)
        if p1 is None or pn is None:
            missing.append(r["Refs"])
            price = ""
        else:
            total_1 += p1[0] * qty
            total_n += pn[0] * qty
            sources.add(pn[2])
            currencies |= {p1[1], pn[1]}
            price = f"{pn[0]:.3f}" + ("" if pn[2] == prices.preference[0] else f" ({pn[2]})")
        order = " ".join(_link(name, r.get(f[role], "")) for role, name in (("digikey", "DigiKey"), ("mouser", "Mouser")) if r.get(f[role], "").strip())
        out_rows.append([r["Refs"].replace(",", " "), qty, r["Value"], r[f["manufacturer"]], _link(r[f["mpn"]], r.get(f.get("datasheet", ""), "")), order, price, r.get(f.get("notes", ""), "")])
    currency = "/".join(sorted(currencies)) or ""
    header = ["Refs", "Qty", "Value", "Manufacturer", "MPN", "Order", f"Unit price at {boards} boards" + (f" ({currency})" if currency else ""), "Notes"]
    lines = [table(header, out_rows), ""]
    if len(currencies) > 1:
        lines.append(f"Price per board: not summed, more than one currency ({currency}).")
    elif out_rows:
        dates = ", ".join(sorted(prices.dates))
        lines.append(f"Price per board: {total_1:.2f} {currency} at 1 board, {total_n:.2f} {currency} at {boards} boards. Prices: {', '.join(d for d in prices.preference if d in sources)}, {dates}.")
    if missing:
        lines.append(f"No price: {', '.join(m.replace(',', ' ') for m in missing)}.")
    total, smd, tht, other = part_count(pcb_root)
    lines.append(f"Parts per board: {total} (SMD {smd}, THT {tht}" + (f", other {other}" if other else "") + ").")
    return "\n".join(lines)
