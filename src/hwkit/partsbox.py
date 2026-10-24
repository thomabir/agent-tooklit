"""PartsBox API (https://partsbox.com/api.html): stock of the BOM parts, and a project with the BOM.

API key: environment variable PARTSBOX_API_KEY, else the line PARTSBOX_API_KEY=... in ~/.partsbox/.env. The key is never printed.
"""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.partsbox.com/api/1"
ENV_FILE = Path("~/.partsbox/.env").expanduser()
TIMEOUT = 30  # s
SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "": 1.0, "R": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}
_VALUE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*([pnuµμmRkKMG]?)(\d*)\s*(?:F|H|Ω|Ohm|ohm|R)?(?![\w])")
_PACKAGE = re.compile(r"(?<!\d)(01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)(?!\d)")


def api_key():
    if os.environ.get("PARTSBOX_API_KEY"):
        return os.environ["PARTSBOX_API_KEY"]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "PARTSBOX_API_KEY":
                return v.strip().strip("'\"")
    raise RuntimeError(f"no PartsBox API key: set PARTSBOX_API_KEY or write it into {ENV_FILE}")


class Client:
    def __init__(self, key=None):
        self._key = key or api_key()

    def call(self, op, **params):
        req = urllib.request.Request(f"{API}/{op}", data=json.dumps(params).encode(), headers={"Content-Type": "application/json", "Authorization": f"APIKey {self._key}"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"PartsBox {op}: {e.code} {e.reason}: {e.read()[:300]!r}") from None
        if body.get("partsbox.status/category") != "status/ok":
            raise RuntimeError(f"PartsBox {op}: {body.get('partsbox.status/message')}")
        return body.get("data")

    def parts(self):
        return self.call("part/all")

    def on_hand(self, part_id):
        """On-hand quantity: sum of the storage sources without a status (part/storage; the stock history is not a stock count)."""
        return sum(s.get("source/quantity", 0) for s in self.call("part/storage", **{"part/id": part_id}) or [] if not s.get("source/status"))


def value_number(text):
    """Numeric values with SI prefixes in a text, in base units. "4k7" = 4700, "100nF" = 1e-7, "10 kΩ" = 1e4."""
    found = []
    for m in _VALUE.finditer(text):
        mantissa, prefix, tail = m.groups()
        if tail and "." in mantissa:
            continue
        found.append(float(f"{mantissa}.{tail}" if tail else mantissa) * SI[prefix])
    return found


def package(text):
    """Imperial chip size (0402, 0603, ...) in a footprint name or a text, or None."""
    m = _PACKAGE.search(text or "")
    return m.group(1) if m else None


def _same(a, b):
    return abs(a - b) <= 1e-9 * max(abs(a), abs(b))


def candidates(row, fields, parts):
    """Stock parts with the same chip size and the same value as a BOM line. Heuristic list for a human or agent decision."""
    pkg = package(row.get("Footprint", ""))
    values = value_number(row.get("Value", ""))
    if not pkg or not values:
        return []
    out = []
    for p in parts:
        text = " ".join(str(p.get(k) or "") for k in ("part/name", "part/description", "part/footprint"))
        if package(text) == pkg and any(_same(v, w) for v in values for w in value_number(text)):
            out.append(p)
    return out


def stock_report(client, rows, fields, boards):
    """rows: BOM rows without DNP lines (merged by part). Returns (lines, notes, stock); stock: {MPN: on-hand quantity} of the exact MPN matches."""
    parts = client.parts()
    by_mpn = {}
    for p in parts:
        if p.get("part/mpn"):
            by_mpn.setdefault(p["part/mpn"].strip().upper(), []).append(p)
    lines, notes, stock = [], [], {}
    for r in rows:
        need = int(r["Qty"]) * boards
        refs = r["Refs"].replace(",", " ")
        mpn = r[fields["mpn"]].strip()
        exact = by_mpn.get(mpn.upper(), [])
        if exact:
            p = exact[0]
            have = client.on_hand(p["part/id"])
            stock[mpn] = have
            low = (p.get("part/low-stock") or {}).get("report")
            lines.append(f"{refs}: {mpn} in stock: {have}, need {need}")
            if have < need:
                notes.append(f"{refs}: {mpn}: stock {have} < need {need}")
            elif low is not None and have - need < low:
                notes.append(f"{refs}: {mpn}: stock after the build {have - need} < low-stock level {low}")
            continue
        cands = candidates(r, fields, parts)
        if not cands:
            lines.append(f"{refs}: {mpn} not in stock")
            continue
        lines.append(f"{refs}: {mpn} not in stock; candidates (same size and value):")
        for p in cands:
            lines.append(f"  {p.get('part/name', '')} | {p.get('part/mpn', '')} | {p.get('part/description', '')} | on hand {client.on_hand(p['part/id'])}")
    return lines, notes, stock


def entries(rows, fields, parts):
    """Project entries: stock part by MPN, else a named entry (MPN, manufacturer and value in the comments)."""
    by_mpn = {p["part/mpn"].strip().upper(): p for p in parts if p.get("part/mpn")}
    out = []
    for i, r in enumerate(rows):
        mpn = r[fields["mpn"]].strip()
        e = {"entry/quantity": int(r["Qty"]), "entry/designators": [d.strip() for d in r["Refs"].split(",") if d.strip()], "entry/order": i}
        p = by_mpn.get(mpn.upper())
        if p:
            e["entry/part-id"] = p["part/id"]
        else:
            e["entry/name"] = mpn
            e["entry/comments"] = f"{r[fields['manufacturer']]}, {r['Value']}"
        out.append(e)
    return out


def sync_project(client, name, rows, fields):
    """Create the project, or replace all entries of the project with this name. Returns (project id, created)."""
    new = entries(rows, fields, client.parts())
    existing = [p for p in client.call("project/all") or [] if p.get("project/name") == name]
    if not existing:
        pid = client.call("project/create", **{"project/name": name, "entries": new})["project/id"]
        return pid, True
    pid = existing[0]["project/id"]
    old = client.call("project/get-entries", **{"project/id": pid}) or []
    if old:
        client.call("project/delete-entries", **{"project/id": pid, "ids": [e["entry/id"] for e in old]})
    client.call("project/add-entries", **{"project/id": pid, "entries": new})
    got = client.call("project/get-entries", **{"project/id": pid}) or []
    if len(got) != len(new):
        raise RuntimeError(f"PartsBox project {name}: {len(got)} entries, expected {len(new)}")
    return pid, False
