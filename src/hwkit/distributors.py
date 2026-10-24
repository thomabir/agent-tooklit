"""Distributor part lookup by manufacturer and MPN: DigiKey Product Information API v4, Mouser Search API v1.

Credentials: file credentials_path() (TOML, sections [digikey] client_id, client_secret, optional sandbox = true, and [mouser] api_key). The environment variables in ENV override the file values.
"""

import json
import os
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

ENV = {
    ("digikey", "client_id"): "DIGIKEY_CLIENT_ID",
    ("digikey", "client_secret"): "DIGIKEY_CLIENT_SECRET",
    ("digikey", "sandbox"): "DIGIKEY_SANDBOX",
    ("mouser", "api_key"): "MOUSER_API_KEY",
}
REEL_PACKAGES = ("Tape & Reel", "Digi-Reel")  # full-reel packaging, not for prototype quantities
TIMEOUT = 30  # s


def credentials_path():
    return Path(os.environ.get("HWKIT_CREDENTIALS", "~/.config/hwkit/credentials.toml")).expanduser()


def load_credentials():
    """{section: {key: value}} from the credentials file and the environment."""
    path = credentials_path()
    creds = tomllib.loads(path.read_text()) if path.exists() else {}
    for (section, key), var in ENV.items():
        if os.environ.get(var):
            creds.setdefault(section, {})[key] = os.environ[var]
    return creds


@dataclass(frozen=True)
class Offer:
    part_number: str
    url: str
    manufacturer: str
    mpn: str
    package: str
    stock: int
    breaks: tuple  # ((quantity, unit price), ...), ascending quantity
    currency: str
    datasheet: str = ""

    def price_at(self, quantity):
        """Unit price at an order quantity, or None if the quantity is below the first price break."""
        prices = [p for q, p in self.breaks if q <= quantity]
        return prices[-1] if prices else None

    @property
    def unit_price(self):
        return self.price_at(1)


class Distributor:
    """A distributor that finds an offer for a manufacturer part. roles: {schematic field role: Offer attribute}."""

    name = ""
    roles: ClassVar[dict] = {}

    def lookup(self, manufacturer, mpn, part_number=None):
        """Returns (offer or None, note). part_number: distributor part number that selects the packaging variant."""
        raise NotImplementedError


def _request(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.reason} from {url.split('?')[0]}: {e.read()[:300]!r}") from None


def _same_manufacturer(schematic_name, distributor_name):
    """True if the first word of the schematic manufacturer is in the distributor manufacturer name (example: 'Amphenol' and 'Amphenol ICC (Commercial Products)')."""
    words = schematic_name.lower().split()
    return bool(words) and words[0] in distributor_name.lower()


def _breaks(rows, qty_key, price_key):
    found = sorted((int(b[qty_key]), float(b[price_key])) for b in rows if b.get(price_key) not in (None, ""))
    return tuple(found)


class DigiKey(Distributor):
    name = "digikey"
    roles: ClassVar[dict] = {"digikey_pn": "part_number", "digikey": "url", "datasheet": "datasheet"}
    API = "https://api.digikey.com"
    SANDBOX_API = "https://sandbox-api.digikey.com"  # for apps made in the DigiKey sandbox; the production API rejects their client ID

    def __init__(self, client_id, client_secret, site, language, currency, sandbox=False):
        self.api = self.SANDBOX_API if sandbox else self.API
        self.client_id = client_id
        self.client_secret = client_secret
        self.locale = {"X-DIGIKEY-Locale-Site": site, "X-DIGIKEY-Locale-Language": language, "X-DIGIKEY-Locale-Currency": currency}
        self.currency = currency
        self._token = None

    def _headers(self):
        if self._token is None:
            form = urllib.parse.urlencode({"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"}).encode()
            try:
                self._token = _request(f"{self.api}/v1/oauth2/token", form, {"Content-Type": "application/x-www-form-urlencoded"})["access_token"]
            except RuntimeError as e:
                if str(e).startswith("401"):
                    raise RuntimeError(f"{e}\nA sandbox app has a different client ID and no product search: make a production app with 'ProductInformation V4' on developer.digikey.com.") from None
                raise
        return {"X-DIGIKEY-Client-Id": self.client_id, "Authorization": f"Bearer {self._token}", "Content-Type": "application/json", **self.locale}

    def _products(self, mpn):
        body = json.dumps({"Keywords": mpn, "Limit": 20, "Offset": 0}).encode()
        r = _request(f"{self.api}/products/v4/search/keyword", body, self._headers())
        return (r.get("ExactMatches") or []) + (r.get("Products") or [])

    @staticmethod
    def _variation(product, part_number=None):
        """Packaging variation: the one with part_number, else for small quantities: no full reel, lowest minimum order quantity, then most stock."""
        variations = product.get("ProductVariations") or []
        if part_number:
            return next((v for v in variations if v["DigiKeyProductNumber"] == part_number), None)
        variations = [v for v in variations if not any(p in v["PackageType"]["Name"] for p in REEL_PACKAGES)]
        if not variations:
            return None
        return min(variations, key=lambda v: (v.get("MinimumOrderQuantity") or 1, -(v.get("QuantityAvailableforPackageType") or 0)))

    def lookup(self, manufacturer, mpn, part_number=None):
        found, seen = [], set()
        for p in self._products(mpn):
            key = (p["ManufacturerProductNumber"], p["Manufacturer"]["Name"])
            if p["ManufacturerProductNumber"].upper() == mpn.upper() and _same_manufacturer(manufacturer, p["Manufacturer"]["Name"]) and key not in seen:
                seen.add(key)
                found.append(p)
        if not found:
            return None, "no exact MPN match"
        if len(found) > 1:
            return None, "several products: " + ", ".join(f"{p['Manufacturer']['Name']} {p['ProductUrl']}" for p in found)
        p = found[0]
        v = self._variation(p, part_number)
        if v is None:
            return None, f"no variation {part_number}" if part_number else "only full-reel packaging"
        status = (p.get("ProductStatus") or {}).get("Status", "")
        offer = Offer(
            part_number=v["DigiKeyProductNumber"],
            url=p["ProductUrl"],
            manufacturer=p["Manufacturer"]["Name"],
            mpn=p["ManufacturerProductNumber"],
            package=v["PackageType"]["Name"],
            stock=int(v.get("QuantityAvailableforPackageType") or 0),
            breaks=_breaks(v.get("StandardPricing") or [], "BreakQuantity", "UnitPrice"),
            currency=self.currency,
            datasheet=p.get("DatasheetUrl") or "",
        )
        return offer, status


class Mouser(Distributor):
    name = "mouser"
    roles: ClassVar[dict] = {"mouser_pn": "part_number", "mouser": "url"}
    API = "https://api.mouser.com/api/v1"

    def __init__(self, api_key, currency):
        self.api_key = api_key
        self.currency = currency

    def lookup(self, manufacturer, mpn, part_number=None):
        body = json.dumps({"SearchByPartRequest": {"mouserPartNumber": part_number or mpn, "partSearchOptions": "Exact"}}).encode()
        r = _request(f"{self.API}/search/partnumber?apiKey={self.api_key}", body, {"Content-Type": "application/json"})
        if r.get("Errors"):
            raise RuntimeError(f"Mouser: {r['Errors']}")
        found = [p for p in (r.get("SearchResults") or {}).get("Parts") or [] if p["ManufacturerPartNumber"].upper() == mpn.upper() and _same_manufacturer(manufacturer, p["Manufacturer"])]
        if part_number:
            found = [p for p in found if p["MouserPartNumber"] == part_number]
        if not found:
            return None, "no exact MPN match"
        p = max(found, key=lambda p: int(p.get("AvailabilityInStock") or 0))
        breaks = [{"Quantity": b["Quantity"], "Price": re.sub(r"[^\d.]", "", b["Price"].replace(",", "."))} for b in p.get("PriceBreaks") or []]
        offer = Offer(
            part_number=p["MouserPartNumber"],
            url=p["ProductDetailUrl"],
            manufacturer=p["Manufacturer"],
            mpn=p["ManufacturerPartNumber"],
            package="",
            stock=int(p.get("AvailabilityInStock") or 0),
            breaks=_breaks(breaks, "Quantity", "Price"),
            currency=self.currency,
            datasheet=p.get("DataSheetUrl") or "",
        )
        return offer, p.get("LifecycleStatus") or ""


def configured(lab):
    """Distributors with credentials, in order of preference. Returns (distributors, notes about the missing ones)."""
    creds, cfg = load_credentials(), lab["distributors"]
    found, notes = [], []
    dk = creds.get("digikey", {})
    if dk.get("client_id") and dk.get("client_secret"):
        found.append(DigiKey(dk["client_id"], dk["client_secret"], cfg["digikey"]["site"], cfg["digikey"]["language"], cfg["digikey"]["currency"], str(dk.get("sandbox", False)).lower() in ("true", "1")))
    else:
        notes.append(f"digikey: no client_id/client_secret in {credentials_path()} or environment")
    ms = creds.get("mouser", {})
    if ms.get("api_key"):
        found.append(Mouser(ms["api_key"], cfg["mouser"]["currency"]))
    else:
        notes.append(f"mouser: no api_key in {credentials_path()} or environment")
    return found, notes
