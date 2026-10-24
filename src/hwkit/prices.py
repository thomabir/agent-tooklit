"""Price cache: distributor price breaks per part in a CSV file, so that a README update needs no network.

One row per price break: manufacturer, mpn, distributor, part_number, quantity, unit_price, currency, date.
"""

import csv
import datetime
from pathlib import Path

COLUMNS = ("manufacturer", "mpn", "distributor", "part_number", "quantity", "unit_price", "currency", "date")


def fetch(distributors, parts, today=None):
    """parts: [(manufacturer, mpn, {distributor name: part number or ""})]. Returns (rows, issues)."""
    today = today or datetime.date.today().isoformat()
    rows, issues = [], []
    for manufacturer, mpn, part_numbers in parts:
        for d in distributors:
            try:
                offer, note = d.lookup(manufacturer, mpn, part_numbers.get(d.name) or None)
            except RuntimeError as e:
                issues.append(f"{d.name}: {manufacturer} {mpn}: {e}")
                continue
            if offer is None:
                issues.append(f"{d.name}: {manufacturer} {mpn}: {note}")
                continue
            if not offer.breaks:
                issues.append(f"{d.name}: {manufacturer} {mpn}: no price")
            for q, p in offer.breaks:
                rows.append({"manufacturer": manufacturer, "mpn": mpn, "distributor": d.name, "part_number": offer.part_number, "quantity": q, "unit_price": p, "currency": offer.currency, "date": today})
    return rows, issues


def write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        w.writerows(rows)


class Prices:
    """Price lookup from a cache file. preference: distributor names, first = preferred."""

    def __init__(self, path, preference=("digikey", "mouser")):
        self.preference = preference
        self.breaks = {}  # (manufacturer, mpn, distributor) -> [(quantity, unit price)]
        self.currency, self.dates = {}, set()
        if path and Path(path).is_file():
            with open(path, newline="") as f:
                for r in csv.DictReader(f):
                    key = (r["manufacturer"], r["mpn"], r["distributor"])
                    self.breaks.setdefault(key, []).append((int(r["quantity"]), float(r["unit_price"])))
                    self.currency[r["distributor"]] = r["currency"]
                    self.dates.add(r["date"])
        for b in self.breaks.values():
            b.sort()

    def unit_price(self, manufacturer, mpn, quantity):
        """(unit price, currency, distributor) at an order quantity from the first distributor in preference with a price, or None."""
        for d in self.preference:
            prices = [p for q, p in self.breaks.get((manufacturer, mpn, d), []) if q <= quantity]
            if prices:
                return prices[-1], self.currency[d], d
        return None
