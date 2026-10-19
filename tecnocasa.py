"""Tecnocasa client and normalizers.

Data source: the public JSON endpoints behind https://www.tecnocasa.it.
Read-only; no authentication.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import json
import logging
import random
import re
import time
import unicodedata
from typing import Any, Iterable, Literal, Sequence
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.tecnocasa.it"

log = logging.getLogger(__name__)

# The portal's WAF stalls plain curl/urllib requests. Browser-like headers are
# required for reliable access.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.tecnocasa.it/",
    "Origin": "https://www.tecnocasa.it",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

CONTRACT_MAP = {
    "sale": "acquis",
    "buy": "acquis",
    "vendita": "acquis",
    "acquis": "acquis",
    "rent": "locazi",
    "rental": "locazi",
    "affitto": "locazi",
    "locazi": "locazi",
}

SECTOR_MAP = {
    "residential": "res",
    "residenziale": "res",
    "res": "res",
    "industrial": "ind",
    "commercial": "ind",
    "commerciale": "ind",
    "ind": "ind",
    "touristic": "tur",
    "turistico": "tur",
    "tur": "tur",
    "construction": "can",
    "nuove-costruzioni": "can",
    "can": "can",
}

TYPE_MAP = {
    "districts": "district",
    "district": "district",
    "quarters": "quarter",
    "quarter": "quarter",
    "cities": "city",
    "city": "city",
    "provinces": "province",
    "province": "province",
    "regions": "region",
    "region": "region",
    "estates": "estate",
    "estate": "estate",
}

PROPERTY_TYPE_TERMS = {
    "apartment": [
        "appartament", "bilocale", "trilocale", "monolocale", "quadrilocale",
        "attico", "loft", "penthouse", "mansarda", "locale",
    ],
    "house": ["villa", "ville", "casa", "casale", "rustico", "villetta", "schiera", "indipendente"],
    "garage": ["box", "posto auto", "garage", "autorimessa", "parcheggio"],
    "commercial": ["negozio", "ufficio", "magazzino", "capannone", "commerciale", "laboratorio"],
    "land": ["terreno", "terreni"],
    "room": ["stanza", "camera", "posto letto"],
}

BATCH_SIZE = 60

# /api/estates/search is the same endpoint the portal's own listing page uses.
# It returns fully normalised summaries and supports server-side filtering,
# sorting and pagination, so a search is one request instead of a map call plus
# one detail batch per 20 listings.
MAX_SEARCH_LIMIT = 200

# The portal's edge alternates between fast responses (0.5-3s) and stalls that
# never answer. Short attempts plus a few retries beat one long timeout.
API_ATTEMPTS = 3
API_TIMEOUT = 6.0
API_RETRY_BASE = 0.4
API_MIN_INTERVAL = 0.25
API_CONCURRENCY = 3
API_COOLDOWN = 20.0

HTML_ATTEMPTS = 3
HTML_TIMEOUT = 10.0
HTML_RETRY_BASE = 0.6
HTML_CONCURRENCY = 5

ENRICH_CONCURRENCY = 5
ENRICH_BUDGET = 35.0

CACHE_MAX_ENTRIES = 512
STALE_MAX = 7 * 24 * 3600
REFRESH_RETRY_SECONDS = 20.0

SEARCH_SORT_MAP = {
    "price_asc": "Prezzo|ASC",
    "price_desc": "Prezzo|DESC",
    "sqm_asc": "MQ|ASC",
    "sqm_desc": "MQ|DESC",
    "rooms_asc": "Camere|ASC",
    "rooms_desc": "Camere|DESC",
}

# Franchise microsites are numbered subdomains per city: milano1..milanoN,
# roma1..etc. They are served by a different application than the national
# portal and generally stay reachable when www.tecnocasa.it does not.
MICROSITE_TEMPLATE = "https://{city}{index}.tecnocasa.it"
MICROSITE_PROBE_TTL = 6 * 3600
MICROSITE_PAGE_TTL = 300
DEFAULT_MAX_MICROSITE_INDEX = 120


class TecnocasaError(RuntimeError):
    """Raised when Tecnocasa cannot be reached or returns unusable data."""


class TecnocasaNotFound(TecnocasaError):
    """Raised when a listing or page does not exist."""


# ---------------------------------------------------------------------------
# Small parsing helpers
# ---------------------------------------------------------------------------


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower()).strip()


def strip_html(value: Any) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)).strip()


def parse_number(value: Any) -> float | None:
    """Parse Italian-formatted numbers: € 395.000 -> 395000, 50,00 -> 50.0."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d[\d.,]*", str(value))
    if not match:
        return None
    raw = match.group(0).rstrip(".,")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def to_int(value: Any) -> int | None:
    number = parse_number(value)
    if number is None:
        return None
    try:
        return int(round(number))
    except (ValueError, OverflowError):
        return None


def parse_price(value: Any) -> int | None:
    return to_int(value)


def parse_surface(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"(\d[\d.,]*)\s*(?:mq|m²|m2|metri)", str(value), re.I)
    if not match:
        match = re.search(r"(?:mq|m²|m2|metri)\s*(\d[\d.,]*)", str(value), re.I)
    return to_int(match.group(1)) if match else to_int(value)


def parse_rooms(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"(\d+)\s*(?:local|stanz|van|settiman)", str(value), re.I)
    return int(match.group(1)) if match else to_int(value)


def parse_bathrooms(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"(\d+)\s*bagn", str(value), re.I)
    return int(match.group(1)) if match else to_int(value)


def image_url(item: dict[str, Any]) -> str | None:
    images = item.get("images") or []
    if images:
        url = images[0].get("url") or {}
        return url.get("card") or url.get("detail") or url.get("gallery")
    media = item.get("media") or {}
    media_images = media.get("images") or []
    if media_images:
        url = media_images[0].get("url") or {}
        return url.get("card") or url.get("detail") or url.get("gallery")
    return None


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def normalize_agency(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if not isinstance(value, dict):
        return {"id": value}
    return {
        "id": value.get("id"),
        "name": value.get("name"),
        "address": value.get("address"),
        "district": value.get("district"),
        "email": value.get("email"),
        "phone": value.get("phone"),
        "mobile": value.get("mobile"),
        "whatsapp": value.get("whatsapp"),
        "microsite_url": value.get("UrlSitoAgenzia") or value.get("url_site"),
        "area_url": value.get("url_agency"),
        "profile_url": value.get("url_site"),
        "latitude": value.get("latitude"),
        "longitude": value.get("longitude"),
    }


def normalize_summary(item: dict[str, Any]) -> dict[str, Any]:
    agency = item.get("agency") or {}
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "subtitle": item.get("subtitle"),
        "price": item.get("price"),
        "price_value": parse_price(item.get("price")),
        "surface": item.get("surface"),
        "surface_value": parse_surface(item.get("surface")),
        "rooms": item.get("rooms"),
        "rooms_value": parse_rooms(item.get("rooms")),
        "bathrooms": item.get("bathrooms"),
        "bathrooms_value": parse_bathrooms(item.get("bathrooms")),
        "agency_id": agency.get("id") if isinstance(agency, dict) else agency,
        "detail_url": item.get("detail_url"),
        "image": image_url(item),
        "exclusive": item.get("exclusive"),
        "discount": item.get("discount"),
        "previous_price": item.get("previous_price"),
        "virtual_tour": item.get("virtual_tour"),
        "top": item.get("top"),
        "ad_type": item.get("ad_type"),
    }


def normalize_estate(estate: dict[str, Any], summary: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = summary or {}
    data_rows = estate.get("data") or []
    details: dict[str, Any] = {}
    for row in data_rows:
        if isinstance(row, dict) and row.get("label"):
            value = row.get("valore")
            if isinstance(value, str):
                value = html_lib.unescape(value)
            details[row["label"]] = value

    features = estate.get("features") or {}
    media = estate.get("media") or {}
    energy = estate.get("energy_data") or {}
    costs = estate.get("costs") or {}
    city = estate.get("city") or {}
    district = estate.get("district") or {}
    quarter = estate.get("quarter") or {}
    province = estate.get("province") or {}
    region = estate.get("region") or {}
    contract = estate.get("contract") or {}
    sector = estate.get("sector") or {}
    prop_type = estate.get("type") or {}

    images: list[str] = []
    for image in media.get("images") or []:
        url = image.get("url") or {}
        chosen = url.get("detail") or url.get("gallery") or url.get("card")
        if chosen:
            images.append(chosen)
    if not images and summary.get("image"):
        images = [summary["image"]]

    price_value = to_int(estate.get("numeric_price")) or parse_price(estate.get("price")) or summary.get("price_value")
    surface_value = to_int(estate.get("numeric_surface")) or parse_surface(estate.get("surface")) or summary.get("surface_value")
    rooms_value = parse_rooms(estate.get("rooms")) or summary.get("rooms_value")
    bathrooms_value = parse_bathrooms(estate.get("bathrooms") or details.get("Bagni")) or summary.get("bathrooms_value")
    bedrooms_value = features.get("bedrooms") or to_int(details.get("Camere da letto"))

    return {
        **summary,
        "id": estate.get("id") or summary.get("id"),
        "title": estate.get("title") or summary.get("title"),
        "subtitle": estate.get("subtitle") or summary.get("subtitle"),
        "price": estate.get("price") or summary.get("price"),
        "price_value": price_value,
        "surface": estate.get("surface") or summary.get("surface"),
        "surface_value": surface_value,
        "rooms": estate.get("rooms") or summary.get("rooms"),
        "rooms_value": rooms_value,
        "bathrooms": estate.get("bathrooms") or summary.get("bathrooms"),
        "bathrooms_value": bathrooms_value,
        "bedrooms_value": bedrooms_value,
        "address": details.get("Indirizzo") or estate.get("address"),
        "postal_code": details.get("Cap"),
        "city": city.get("title"),
        "district": district.get("title") if isinstance(district, dict) else district,
        "quarter": quarter.get("title") if isinstance(quarter, dict) else quarter,
        "province": province.get("title") if isinstance(province, dict) else province,
        "region": region.get("title") if isinstance(region, dict) else region,
        "contract": contract.get("title") if isinstance(contract, dict) else contract,
        "sector": sector.get("title") if isinstance(sector, dict) else sector,
        "property_type": prop_type.get("title") if isinstance(prop_type, dict) else prop_type,
        "energy_class": (energy.get("class") or "").upper() or None,
        "expenses": costs.get("expenses"),
        "floor": features.get("floor"),
        "features": {
            "elevator": features.get("elevator_immo"),
            "air_conditioning": features.get("air_conditioning_immo"),
            "garden": features.get("garden"),
            "balcony": features.get("balconies"),
            "terrace": features.get("terraces"),
            "garage": features.get("box"),
            "parking": features.get("car_places"),
            "furnished": features.get("furnitured"),
            "heating": features.get("heating_immo") or estate.get("heating"),
            "condition": estate.get("building_state"),
            "concierge": features.get("concierge"),
            "free": features.get("free"),
            "property_type": features.get("property_type"),
            "build_year": features.get("build_year"),
        },
        "description": strip_html(estate.get("description")),
        "description_html": estate.get("description"),
        "agency": normalize_agency(estate.get("agency")) or normalize_agency(summary.get("agency")),
        "images": images,
        "coordinates": {
            "lat": estate.get("latitude"),
            "lon": estate.get("longitude"),
        },
        "published_at": estate.get("last_published_at"),
        "exclusive": estate.get("exclusive") if estate.get("exclusive") is not None else summary.get("exclusive"),
        "url": estate.get("detail_url") or summary.get("detail_url"),
        "details": details,
    }


def normalize_autocomplete(data: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(items: Any, default_type: str | None) -> None:
        if isinstance(items, dict):
            items = list(items.values())
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            label = strip_html(item.get("placeholder") or item.get("name") or "")
            name = strip_html(item.get("name") or label)
            kind = item.get("type") or default_type
            candidates.append(
                {
                    "type": TYPE_MAP.get(str(kind).lower(), kind),
                    "id": item.get("id"),
                    "name": name,
                    "label": label or name,
                    "city_id": item.get("city_id"),
                    "province_id": item.get("province_id"),
                    "count": item.get("total") or item.get("count"),
                }
            )

    if isinstance(data, dict):
        for key, kind in (
            ("districts", "district"),
            ("quarters", "quarter"),
            ("cities", "city"),
            ("provinces", "province"),
            ("regions", "region"),
            ("estates", "estate"),
        ):
            add(data.get(key), kind)
        precise = data.get("precise")
        if isinstance(precise, dict):
            for key, items in precise.items():
                add(items, key.rstrip("s"))
    elif isinstance(data, list):
        add(data, None)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for candidate in candidates:
        key = (candidate.get("type"), candidate.get("id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def parse_estate_html(page: str) -> dict[str, Any]:
    """Extract the full estate object embedded in a detail page."""
    match = re.search(r':estate="(\{.*?\})"', page, re.S)
    if not match:
        match = re.search(r":estate='(\{.*?\})'", page, re.S)
    if not match:
        raise TecnocasaNotFound("Listing detail payload not found in the page")
    raw = html_lib.unescape(match.group(1))
    try:
        estate = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TecnocasaError(f"Could not decode listing detail JSON: {exc}") from exc
    if not isinstance(estate, dict):
        raise TecnocasaError("Listing detail payload is not an object")
    return estate


def parse_microsite_cards(page: str, base_url: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse franchise microsite listing cards.

    Returns (cards, meta) where meta contains agency/title information.
    """
    soup = BeautifulSoup(page, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    canonical = soup.select_one('link[rel="canonical"]')
    canonical_url = canonical.get("href") if canonical else base_url

    cards: list[dict[str, Any]] = []
    for card in soup.select("div.estate-card"):
        link = card.select_one("a.hover-link[href]")
        if not link:
            continue
        price_el = card.select_one(".estate-card-current-price")
        title_el = card.select_one(".estate-card-title")
        subtitle_el = card.select_one(".estate-card-subtitle")
        data_el = card.select_one(".estate-card-data")
        price = price_el.get_text(" ", strip=True) if price_el else None
        data_text = data_el.get_text(" ", strip=True) if data_el else ""
        cards.append(
            {
                "id": to_int(card.get("immobileid") or card.get("immobileId")),
                "agency_id": card.get("agenziaid") or card.get("agenziaId"),
                "detail_url": httpx.URL(base_url).join(link.get("href")).__str__(),
                "title": title_el.get_text(" ", strip=True) if title_el else None,
                "subtitle": subtitle_el.get_text(" ", strip=True) if subtitle_el else None,
                "price": price,
                "price_value": parse_price(price),
                "surface_value": parse_surface(data_text),
                "rooms_value": parse_rooms(data_text),
                "card_text": data_text,
            }
        )

    agency_name = title.split(" - ")[0].strip() if title else None
    agency_id = next((card.get("agency_id") for card in cards if card.get("agency_id")), None)
    area_links: list[str] = []
    origin = f"{urlparse(canonical_url).scheme}://{urlparse(canonical_url).netloc}"
    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = httpx.URL(canonical_url).join(href).__str__()
        if not absolute.startswith(origin):
            continue
        path = urlparse(absolute).path
        if any(path.startswith(prefix) for prefix in ("/web/", "/privacy/", "/controller")):
            continue
        if absolute not in area_links:
            area_links.append(absolute)

    meta = {
        "title": title,
        "agency_name": agency_name,
        "agency_id": agency_id,
        "microsite_url": origin,
        "area_url": canonical_url,
        "area_links": area_links[:50],
    }
    return cards, meta


def parse_microsite_agency(page: str) -> dict[str, Any]:
    """Extract the franchise agency block from a microsite page."""
    soup = BeautifulSoup(page, "html.parser")
    name = None
    heading = soup.find("h2")
    if heading:
        candidate = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
        if candidate and not candidate.startswith("#") and len(candidate) <= 80:
            name = candidate
    phone = next(
        (anchor.get("href", "")[4:].strip() for anchor in soup.select('a[href^="tel:"]')),
        None,
    )
    email = next(
        (
            anchor.get("href", "")[7:].strip()
            for anchor in soup.select('a[href^="mailto:"]')
            if anchor.get("href", "").endswith("@tecnocasa.it")
        ),
        None,
    )
    return {"name": name, "phone": phone or None, "email": email}


def split_subtitle(subtitle: Any) -> tuple[str, str | None]:
    """Split "Milano, Via Kramer - Porta Venezia" into (address, area)."""
    text = re.sub(r"\s+", " ", str(subtitle or "")).strip()
    if " - " in text:
        address, area = text.rsplit(" - ", 1)
        return address.strip(" ,"), area.strip() or None
    return text, None


def card_to_listing(card: dict[str, Any], host: str) -> dict[str, Any]:
    """Normalize a microsite card into the listing shape used by the tools."""
    address, area = split_subtitle(card.get("subtitle"))
    origin = host if str(host).startswith("http") else f"https://{host}"
    return {
        "id": card.get("id"),
        "title": card.get("title"),
        "subtitle": card.get("subtitle"),
        "address": address or None,
        "area": area,
        "price": card.get("price"),
        "price_value": card.get("price_value"),
        "surface_value": card.get("surface_value"),
        "rooms_value": card.get("rooms_value"),
        "bathrooms_value": parse_bathrooms(card.get("card_text")),
        "agency_id": card.get("agency_id"),
        "detail_url": card.get("detail_url"),
        "microsite_url": origin,
        "image": card.get("image"),
    }


def dedupe_listings(listings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop repeated listing IDs across microsites, keeping the first seen."""
    out: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for listing in listings:
        key = listing.get("id")
        if key is None:
            key = listing.get("detail_url")
        if key is None:
            out.append(listing)
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(listing)
    return out


def filter_listings(
    listings: Iterable[dict[str, Any]],
    *,
    min_price: int | None = None,
    max_price: int | None = None,
    min_sqm: int | None = None,
    max_sqm: int | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    min_bathrooms: int | None = None,
    property_type: str | None = None,
    agency_id: str | None = None,
    areas: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    terms: list[str] | None = None
    if property_type:
        key = normalize_text(property_type)
        terms = PROPERTY_TYPE_TERMS.get(key, [key])

    area_terms = [term for term in (normalize_text(value) for value in areas or []) if term]

    def number_ok(value: Any, minimum: int | None, maximum: int | None) -> bool:
        if minimum is None and maximum is None:
            return True
        parsed = parse_number(value)
        if parsed is None:
            return False
        if minimum is not None and parsed < minimum:
            return False
        if maximum is not None and parsed > maximum:
            return False
        return True

    out: list[dict[str, Any]] = []
    for listing in listings:
        if not number_ok(listing.get("price_value"), min_price, max_price):
            continue
        if not number_ok(listing.get("surface_value"), min_sqm, max_sqm):
            continue
        if not number_ok(listing.get("rooms_value"), min_rooms, max_rooms):
            continue
        if min_bathrooms is not None:
            baths = parse_number(listing.get("bathrooms_value"))
            if baths is None or baths < min_bathrooms:
                continue
        if agency_id and str(listing.get("agency_id") or "") != str(agency_id):
            continue
        if area_terms:
            haystack = normalize_text(
                " ".join(
                    str(listing.get(field) or "")
                    for field in ("subtitle", "address", "area", "title")
                )
            )
            if not any(term in haystack for term in area_terms):
                continue
        if terms:
            haystack = normalize_text(
                " ".join(
                    str(listing.get(field) or "")
                    for field in ("title", "subtitle", "property_type", "description")
                )
            )
            if not any(term in haystack for term in terms):
                continue
        out.append(listing)
    return out


def sort_listings(listings: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    if sort == "relevance":
        return listings
    if sort == "price_asc":
        return sorted(listings, key=lambda x: (x.get("price_value") is None, x.get("price_value") or 0, x.get("id") or 0))
    if sort == "price_desc":
        return sorted(listings, key=lambda x: (x.get("price_value") is None, -(x.get("price_value") or 0), x.get("id") or 0))
    if sort == "sqm_asc":
        return sorted(listings, key=lambda x: (x.get("surface_value") is None, x.get("surface_value") or 0, x.get("id") or 0))
    if sort == "sqm_desc":
        return sorted(listings, key=lambda x: (x.get("surface_value") is None, -(x.get("surface_value") or 0), x.get("id") or 0))
    if sort == "rooms_asc":
        return sorted(listings, key=lambda x: (x.get("rooms_value") is None, x.get("rooms_value") or 0, x.get("id") or 0))
    if sort == "rooms_desc":
        return sorted(listings, key=lambda x: (x.get("rooms_value") is None, -(x.get("rooms_value") or 0), x.get("id") or 0))
    return listings


def build_search_params(
    *,
    city_id: int,
    province: str | None = None,
    contract: str = "acquis",
    sector: str = "res",
    district_ids: Sequence[int] | None = None,
    quarter_ids: Sequence[int] | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_sqm: int | None = None,
    max_sqm: int | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    agency_id: str | None = None,
    sort: str = "relevance",
    limit: int = 20,
    section: str = "estate",
) -> list[tuple[str, Any]]:
    """Build query parameters for /api/estates/search.

    The portal expects `districts`/`quarters` as pipe-separated IDs, and sort
    values as `<field>|<direction>` (e.g. ``Prezzo|ASC``). `min_bathrooms` is
    not supported server-side and is applied by the caller.
    """
    params: list[tuple[str, Any]] = [
        ("section", section),
        ("contract", CONTRACT_MAP.get(contract.lower(), contract)),
        ("sector", SECTOR_MAP.get(sector.lower(), sector)),
        ("city", int(city_id)),
        ("limit", max(1, min(int(limit), MAX_SEARCH_LIMIT))),
    ]
    if province:
        params.append(("province", province))
    if district_ids:
        params.append(("districts", "|".join(str(int(value)) for value in district_ids)))
    if quarter_ids:
        params.append(("quarters", "|".join(str(int(value)) for value in quarter_ids)))
    for name, value in (
        ("min_price", min_price),
        ("max_price", max_price),
        ("min_surface", min_sqm),
        ("max_surface", max_sqm),
        ("min_rooms", min_rooms),
        ("max_rooms", max_rooms),
        ("agency", agency_id),
    ):
        if value is not None:
            params.append((name, value))
    sort_value = SEARCH_SORT_MAP.get(sort)
    if sort_value:
        params.append(("sort", sort_value))
    return params


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class TecnocasaClient:
    def __init__(self, timeout: float = API_TIMEOUT):
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(timeout, connect=5.0),
            follow_redirects=True,
            http2=True,
            limits=httpx.Limits(
                max_connections=API_CONCURRENCY + HTML_CONCURRENCY,
                max_keepalive_connections=6,
            ),
        )
        self._cache: dict[str, tuple[float, Any]] = {}
        self._inflight: dict[str, asyncio.Task[Any]] = {}
        self._retry_after: dict[str, float] = {}
        self._summary_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._timeout = timeout
        self._throttle_lock = asyncio.Lock()
        self._api_semaphore = asyncio.Semaphore(API_CONCURRENCY)
        self._html_semaphore = asyncio.Semaphore(HTML_CONCURRENCY)
        self._last_api_request = 0.0
        self._consecutive_failures = 0
        self._cooldown_until = 0.0
        self._probe_cache: dict[str, tuple[float, float, dict[str, Any]]] = {}

    async def close(self) -> None:
        tasks = list(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._client.aclose()

    async def _cached(
        self,
        key: str,
        ttl: float,
        factory: Any,
        *,
        allow_stale: bool = True,
    ) -> Any:
        """Return a cached value, coalescing concurrent requests.

        Once an entry exists it is served immediately even if it has just
        expired (stale-while-revalidate), so a stalled portal does not block
        the tool call. A background refresh updates it.
        """
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit is not None:
            age = now - hit[0]
            if age < ttl:
                return hit[1]
            if allow_stale and age < STALE_MAX:
                self._schedule_refresh(key, ttl, factory)
                return hit[1]

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._fetch_and_store(key, ttl, factory))
            self._inflight[key] = task

            def forget(finished: asyncio.Task[Any]) -> None:
                if self._inflight.get(key) is finished:
                    self._inflight.pop(key, None)

            task.add_done_callback(forget)
        return await asyncio.shield(task)

    def _schedule_refresh(self, key: str, ttl: float, factory: Any) -> None:
        existing = self._inflight.get(key)
        if existing is not None:
            if not existing.done():
                return
            # The previous fetch finished but its done-callback has not run
            # yet; drop it so the stale entry can be refreshed.
            self._inflight.pop(key, None)
        if time.monotonic() < self._retry_after.get(key, 0.0):
            return
        task = asyncio.create_task(self._fetch_and_store(key, ttl, factory))
        self._inflight[key] = task

        def done(finished: asyncio.Task[Any]) -> None:
            if self._inflight.get(key) is finished:
                self._inflight.pop(key, None)
            if finished.cancelled():
                return
            exc = finished.exception()
            if exc is not None:
                self._retry_after[key] = time.monotonic() + REFRESH_RETRY_SECONDS
                log.debug("background refresh failed for %s: %s", key, exc)

        task.add_done_callback(done)

    async def _fetch_and_store(self, key: str, ttl: float, factory: Any) -> Any:
        value = await factory()
        self._cache[key] = (time.monotonic(), value)
        self._retry_after.pop(key, None)
        if len(self._cache) > CACHE_MAX_ENTRIES:
            oldest = min(self._cache, key=lambda item: self._cache[item][0])
            if oldest != key:
                self._cache.pop(oldest, None)
        return value

    async def _throttle_api(self) -> None:
        """Space request starts without serialising response bodies."""
        async with self._throttle_lock:
            wait = API_MIN_INTERVAL - (time.monotonic() - self._last_api_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_api_request = time.monotonic()

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    async def _request_api(self, path: str, params: Any = None) -> httpx.Response:
        now = time.monotonic()
        if now < self._cooldown_until:
            remaining = int(self._cooldown_until - now) + 1
            raise TecnocasaError(
                "Tecnocasa national API is unreachable or throttling this client; "
                f"retry in about {remaining}s (microsite tools still work)."
            )
        async with self._api_semaphore:
            await self._throttle_api()
            return await self._client.get(
                path,
                params=params,
                timeout=httpx.Timeout(self._timeout, connect=5.0),
            )

    async def _get_json(self, path: str, params: Any = None, ttl: float = 120.0) -> Any:
        key = "json:" + path + ":" + json.dumps(params, sort_keys=True, default=str)

        async def fetch() -> Any:
            last: Exception | None = None
            for attempt in range(API_ATTEMPTS):
                started = time.monotonic()
                try:
                    response = await self._request_api(path, params)
                except httpx.RequestError as exc:
                    last = exc
                    log.debug(
                        "GET %s attempt %d failed in %.2fs: %s",
                        path,
                        attempt + 1,
                        time.monotonic() - started,
                        exc,
                    )
                else:
                    log.debug(
                        "GET %s attempt %d -> %s in %.2fs",
                        path,
                        attempt + 1,
                        response.status_code,
                        time.monotonic() - started,
                    )
                    if response.status_code == 200:
                        try:
                            payload = response.json()
                        except ValueError as exc:
                            last = exc
                        else:
                            self._consecutive_failures = 0
                            self._cooldown_until = 0.0
                            return payload
                    elif response.status_code == 404:
                        raise TecnocasaNotFound(f"Not found: {path}")
                    else:
                        retry_after = self._retry_after_seconds(response)
                        if retry_after is not None and retry_after > API_ATTEMPTS * API_TIMEOUT:
                            self._cooldown_until = time.monotonic() + retry_after
                            raise TecnocasaError(
                                "Tecnocasa asked this client to retry in about "
                                f"{int(retry_after)}s."
                            )
                        last = TecnocasaError(
                            f"HTTP {response.status_code}: {response.text[:200]}"
                        )
                        if response.status_code not in (429, 500, 502, 503, 504):
                            raise last
                        if retry_after is not None and attempt < API_ATTEMPTS - 1:
                            await asyncio.sleep(min(retry_after, 5.0))
                            continue
                if attempt < API_ATTEMPTS - 1:
                    await asyncio.sleep(
                        API_RETRY_BASE * (2**attempt) + random.uniform(0.0, 0.25)
                    )
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                self._cooldown_until = time.monotonic() + API_COOLDOWN
                self._consecutive_failures = 0
            raise TecnocasaError(
                f"Tecnocasa API unavailable ({path}): {type(last).__name__}: {last}"
            ) from last

        return await self._cached(key, ttl, fetch)

    async def _get_html(self, url: str, ttl: float = 600.0) -> str:
        key = "html:" + url

        async def fetch() -> str:
            last: Exception | None = None
            for attempt in range(HTML_ATTEMPTS):
                started = time.monotonic()
                try:
                    async with self._html_semaphore:
                        response = await self._client.get(
                            url, timeout=httpx.Timeout(HTML_TIMEOUT, connect=5.0)
                        )
                except httpx.RequestError as exc:
                    last = exc
                    log.debug(
                        "GET %s attempt %d failed in %.2fs: %s",
                        url,
                        attempt + 1,
                        time.monotonic() - started,
                        exc,
                    )
                else:
                    log.debug(
                        "GET %s attempt %d -> %s in %.2fs",
                        url,
                        attempt + 1,
                        response.status_code,
                        time.monotonic() - started,
                    )
                    if response.status_code == 200 and len(response.text) > 1000:
                        return response.text
                    if response.status_code == 404:
                        raise TecnocasaNotFound(f"Not found: {url}")
                    last = TecnocasaError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                if attempt < HTML_ATTEMPTS - 1:
                    await asyncio.sleep(
                        HTML_RETRY_BASE * (2**attempt) + random.uniform(0.0, 0.2)
                    )
            raise TecnocasaError(
                f"Tecnocasa page unavailable ({url}): {type(last).__name__}: {last}"
            ) from last

        return await self._cached(key, ttl, fetch)

    # -- API methods -----------------------------------------------------

    async def autocomplete(self, query: str, section: str = "estate") -> list[dict[str, Any]]:
        data = await self._get_json(
            "/api/geo/autocomplete",
            {"search": query, "section": section},
            ttl=86400,
        )
        return normalize_autocomplete(data)

    async def search_map(
        self,
        *,
        city_id: int,
        province: str,
        contract: str = "acquis",
        sector: str = "res",
        district_ids: Sequence[int] | None = None,
        quarter_ids: Sequence[int] | None = None,
        section: str = "estate",
        aggregate_locations: bool = False,
    ) -> dict[str, Any]:
        # `aggregate_locations=true` returns map clusters (district IDs), not
        # listing IDs. Keep it false for listing data; the portal's map drawer
        # is the only caller that wants aggregation.
        params: list[tuple[str, Any]] = [
            ("aggregate_locations", "true" if aggregate_locations else "false"),
            ("city", city_id),
            ("contract", CONTRACT_MAP.get(contract.lower(), contract)),
            ("province", province),
            ("sector", SECTOR_MAP.get(sector.lower(), sector)),
            ("section", section),
        ]
        if district_ids:
            params.extend(("districts[]", int(value)) for value in district_ids)
        if quarter_ids:
            params.extend(("quarters[]", int(value)) for value in quarter_ids)
        data = await self._get_json("/api/estates/search-map-list", params, ttl=600)
        if not isinstance(data, dict):
            raise TecnocasaError("Unexpected search response")
        return data

    async def search_page(
        self,
        *,
        city_id: int,
        province: str | None = None,
        contract: str = "acquis",
        sector: str = "res",
        district_ids: Sequence[int] | None = None,
        quarter_ids: Sequence[int] | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        min_sqm: int | None = None,
        max_sqm: int | None = None,
        min_rooms: int | None = None,
        max_rooms: int | None = None,
        agency_id: str | None = None,
        sort: str = "relevance",
        limit: int = 20,
        section: str = "estate",
    ) -> dict[str, Any]:
        """Fetch one page from /api/estates/search.

        The endpoint returns the same normalised summary objects as
        `search-by-ids` plus a `pagination` block. It is the portal's own
        listing endpoint, so price, surface, rooms, agency, district and sort
        filters run server-side.
        """
        params = build_search_params(
            city_id=city_id,
            province=province,
            contract=contract,
            sector=sector,
            district_ids=district_ids,
            quarter_ids=quarter_ids,
            min_price=min_price,
            max_price=max_price,
            min_sqm=min_sqm,
            max_sqm=max_sqm,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            agency_id=agency_id,
            sort=sort,
            limit=limit,
            section=section,
        )
        data = await self._get_json("/api/estates/search", params, ttl=600)
        if not isinstance(data, dict):
            raise TecnocasaError("Unexpected search response")
        return data

    async def details(self, ids: Sequence[int], section: str = "estate") -> list[dict[str, Any]]:
        clean_ids = [int(value) for value in ids if value is not None]
        if not clean_ids:
            return []
        params: list[tuple[str, Any]] = [("ids[]", value) for value in clean_ids]
        params.append(("section", section))
        data = await self._get_json("/api/estates/search-by-ids", params, ttl=1800)
        return data if isinstance(data, list) else []

    async def summaries(self, ids: Sequence[int], ttl: float = 1800.0) -> list[dict[str, Any]]:
        """Return raw summaries for `ids`, fetching only the missing ones.

        Summaries are cached per listing rather than per batch, so pagination,
        overlapping searches and a later `get_listing` reuse the same data.
        """
        now = time.monotonic()
        wanted: list[int] = []
        for value in ids:
            if value is None:
                continue
            item_id = int(value)
            if item_id in wanted:
                continue
            cached = self._summary_cache.get(item_id)
            if cached and now - cached[0] < ttl:
                continue
            wanted.append(item_id)

        if wanted:
            batches = [
                wanted[start : start + BATCH_SIZE]
                for start in range(0, len(wanted), BATCH_SIZE)
            ]

            async def load(batch: list[int]) -> None:
                for item in await self.details(batch):
                    item_id = to_int(item.get("id"))
                    if item_id is None:
                        continue
                    self._summary_cache[item_id] = (time.monotonic(), item)
                    if len(self._summary_cache) > CACHE_MAX_ENTRIES:
                        oldest = min(
                            self._summary_cache,
                            key=lambda key: self._summary_cache[key][0],
                        )
                        if oldest != item_id:
                            self._summary_cache.pop(oldest, None)

            await asyncio.gather(*(load(batch) for batch in batches))

        out: list[dict[str, Any]] = []
        seen: set[int] = set()
        for value in ids:
            if value is None:
                continue
            item_id = int(value)
            if item_id in seen:
                continue
            cached = self._summary_cache.get(item_id)
            if cached:
                seen.add(item_id)
                out.append(cached[1])
        return out

    # -- High-level resolution / search ----------------------------------

    async def resolve_location(self, query: str, city_hint: str | None = None) -> dict[str, Any]:
        attempts: list[tuple[str, str | None]] = [(query, city_hint)]
        if "," in query:
            left, right = [part.strip() for part in query.split(",", 1)]
            attempts.append((left, city_hint or right))

        candidates: list[dict[str, Any]] = []
        last_error: Exception | None = None
        for attempt_query, attempt_hint in attempts:
            try:
                candidates = await self.autocomplete(attempt_query)
            except TecnocasaError as exc:
                last_error = exc
                continue
            if candidates:
                query = attempt_query
                city_hint = attempt_hint
                break
        if not candidates and last_error is not None:
            raise last_error

        q = normalize_text(query)
        q_tokens = set(q.split())
        hint = normalize_text(city_hint) if city_hint else ""

        def score(candidate: dict[str, Any]) -> float:
            name = normalize_text(candidate.get("name"))
            text = normalize_text(candidate.get("label") + " " + name)
            value = 0.0
            if name == q:
                value += 100
            if q and q in text:
                value += 40
            c_tokens = set(text.split())
            if q_tokens:
                value += 30 * len(q_tokens & c_tokens) / len(q_tokens)
            if hint and hint in text:
                value += 25
            if candidate.get("type") == "district":
                value += 5
            return value

        ranked = sorted(candidates, key=score, reverse=True)
        top = ranked[0] if ranked else None
        resolved = None
        if top:
            kind = top.get("type")
            if kind == "district":
                resolved = {
                    "type": "district",
                    "id": top.get("id"),
                    "city_id": top.get("city_id"),
                    "province_id": top.get("province_id"),
                    "name": top.get("name"),
                    "label": top.get("label"),
                    "district_ids": [top.get("id")],
                }
            elif kind == "city":
                resolved = {
                    "type": "city",
                    "id": top.get("id"),
                    "city_id": top.get("id"),
                    "province_id": top.get("province_id"),
                    "name": top.get("name"),
                    "label": top.get("label"),
                }
            else:
                resolved = {
                    "type": kind,
                    "id": top.get("id"),
                    "city_id": top.get("city_id"),
                    "province_id": top.get("province_id"),
                    "name": top.get("name"),
                    "label": top.get("label"),
                    "unsupported": True,
                }
        return {"resolved": resolved, "candidates": ranked[:8]}

    async def search_listings(
        self,
        *,
        location: str | None = None,
        city_id: int | None = None,
        district_ids: Sequence[int] | None = None,
        province: str | None = None,
        contract: str = "sale",
        sector: str = "residential",
        min_price: int | None = None,
        max_price: int | None = None,
        min_sqm: int | None = None,
        max_sqm: int | None = None,
        min_rooms: int | None = None,
        max_rooms: int | None = None,
        min_bathrooms: int | None = None,
        property_type: str | None = None,
        agency_id: str | None = None,
        sort: str = "relevance",
        limit: int = 20,
        offset: int = 0,
        include_details: bool = False,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        contract_code = CONTRACT_MAP.get(contract.lower(), contract)
        sector_code = SECTOR_MAP.get(sector.lower(), sector)

        resolved = None
        candidates: list[dict[str, Any]] = []
        if not city_id and not district_ids:
            if not location:
                raise ValueError("Provide `location`, or `city_id`/`district_ids`.")
            resolution = await self.resolve_location(location)
            resolved = resolution["resolved"]
            candidates = resolution["candidates"]
            if not resolved:
                return {
                    "error": "Location not found. Try a more specific city or neighborhood.",
                    "candidates": candidates,
                }
            if resolved.get("unsupported"):
                return {
                    "error": "Please choose a city or district from the candidates.",
                    "candidates": candidates,
                }
            city_id = resolved.get("city_id")
            district_ids = resolved.get("district_ids")
            province = province or resolved.get("province_id")

        if not city_id:
            raise ValueError(
                "city_id is required (or use `location`); "
                "district_ids alone are not enough."
            )

        notices: list[str] = []
        client_filters = min_bathrooms is not None or bool(property_type)
        fetch_limit = min(offset + limit, MAX_SEARCH_LIMIT)
        if client_filters:
            # min_bathrooms is not supported by /api/estates/search, and the
            # property-type match is keyword based. Fetch the largest page the
            # endpoint allows, then filter locally.
            fetch_limit = MAX_SEARCH_LIMIT
        if offset + limit > MAX_SEARCH_LIMIT:
            notices.append(
                f"offset + limit is capped at {MAX_SEARCH_LIMIT}; "
                "narrow the search for deeper pages."
            )

        data = await self.search_page(
            city_id=int(city_id),
            province=str(province) if province else None,
            contract=contract_code,
            sector=sector_code,
            district_ids=district_ids,
            min_price=min_price,
            max_price=max_price,
            min_sqm=min_sqm,
            max_sqm=max_sqm,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            agency_id=agency_id,
            sort=sort,
            limit=fetch_limit,
        )
        raw_items = [
            item for item in (data.get("estates") or []) if isinstance(item, dict)
        ]
        pagination = data.get("pagination") or {}
        total = to_int(pagination.get("total_items"))
        if total is None:
            total = len(raw_items)

        listings = [normalize_summary(item) for item in raw_items]
        if client_filters:
            listings = filter_listings(
                listings,
                min_bathrooms=min_bathrooms,
                property_type=property_type,
            )
            matched = len(listings)
            if total > len(raw_items):
                notices.append(
                    "Bathroom/property-type filters were applied to the first "
                    f"{len(raw_items)} of {total} listings, so `matched` is an estimate."
                )
        else:
            matched = total

        truncated = bool(client_filters and total > len(raw_items)) or (
            offset + limit > MAX_SEARCH_LIMIT
        )
        page = listings[offset : offset + limit]
        if include_details:
            page = await self._enrich_page(page)

        return {
            "source": "tecnocasa.it",
            "contract": contract_code,
            "sector": sector_code,
            "resolved_location": resolved,
            "location_candidates": candidates[:5],
            "total_in_area": total,
            "total_matching": total,
            "matched": matched,
            "returned": len(page),
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(page) < matched,
            "truncated": truncated,
            "notices": notices,
            "listings": page,
        }

    async def _enrich_page(
        self, items: list[dict[str, Any]], *, budget: float = ENRICH_BUDGET
    ) -> list[dict[str, Any]]:
        """Fetch detail pages concurrently, within a total time budget."""
        if not items:
            return []

        semaphore = asyncio.Semaphore(ENRICH_CONCURRENCY)

        async def one(item: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    return await self.get_listing(item["id"], summary=item)
                except TecnocasaError as exc:
                    return {**item, "detail_error": str(exc)}
                except Exception as exc:  # noqa: BLE001 - one bad page must not fail the page
                    return {**item, "detail_error": f"{type(exc).__name__}: {exc}"}

        tasks = [asyncio.create_task(one(item)) for item in items]
        done, pending = await asyncio.wait(tasks, timeout=budget)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        enriched: dict[Any, dict[str, Any]] = {}
        for task in done:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is not None:
                continue
            item = task.result()
            enriched[item.get("id")] = item

        return [
            enriched.get(
                item.get("id"),
                {**item, "detail_error": "detail fetch exceeded the time budget"},
            )
            for item in items
        ]

    async def get_listing(self, property_id: int, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        if summary is None:
            summaries = await self.summaries([property_id])
            if not summaries:
                raise TecnocasaNotFound(f"Listing {property_id} not found")
            summary = normalize_summary(summaries[0])
        detail_url = summary.get("detail_url")
        if not detail_url:
            return {**summary, "detail_error": "No detail URL returned by the API"}
        try:
            page = await self._get_html(detail_url, ttl=3600)
            estate = parse_estate_html(page)
            return normalize_estate(estate, summary)
        except TecnocasaError as exc:
            return {**summary, "detail_error": str(exc)}

    async def search_franchise_area(
        self,
        url: str,
        *,
        contract: str = "sale",
        scope: Literal["area", "agency"] = "area",
        min_price: int | None = None,
        max_price: int | None = None,
        min_sqm: int | None = None,
        max_sqm: int | None = None,
        min_rooms: int | None = None,
        max_rooms: int | None = None,
        min_bathrooms: int | None = None,
        property_type: str | None = None,
        sort: str = "relevance",
        limit: int = 20,
        offset: int = 0,
        include_details: bool = False,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        if not parsed.netloc.endswith("tecnocasa.it"):
            raise ValueError("URL must be a tecnocasa.it domain")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if scope == "agency":
            contract_code = CONTRACT_MAP.get(contract.lower(), contract)
            path = "/immobili-in-vendita" if contract_code == "acquis" else "/immobili-in-affitto"
            target = origin + path
        else:
            target = url

        page = await self._get_html(target, ttl=300)
        cards, meta = parse_microsite_cards(page, target)
        if not cards and "estate-card" not in page:
            raise TecnocasaError("No listing cards found on the franchise page")

        ids = [card["id"] for card in cards if card.get("id") is not None]
        enrichment_notice = None
        summaries: list[dict[str, Any]] = []
        # Card data already carries price/surface/rooms/agency, so the national
        # API is only needed up front for filters that rely on fields cards do
        # not expose (bathrooms). The visible page is enriched afterwards.
        if ids and min_bathrooms is not None:
            try:
                summaries = await self.summaries(ids)
            except TecnocasaError as exc:
                enrichment_notice = f"Could not enrich listings from the national API: {exc}"
        by_id = {to_int(item.get("id")): normalize_summary(item) for item in summaries}

        listings: list[dict[str, Any]] = []
        for card in cards:
            cid = card.get("id")
            listing = by_id.get(cid)
            if listing is None:
                listing = {
                    "id": cid,
                    "title": card.get("title"),
                    "subtitle": card.get("subtitle"),
                    "price": card.get("price"),
                    "price_value": card.get("price_value"),
                    "surface_value": card.get("surface_value"),
                    "rooms_value": card.get("rooms_value"),
                    "agency_id": card.get("agency_id"),
                    "detail_url": card.get("detail_url"),
                    "image": None,
                }
            else:
                listing["agency_id"] = listing.get("agency_id") or card.get("agency_id")
                listing["detail_url"] = listing.get("detail_url") or card.get("detail_url")
            listings.append(listing)

        filtered = filter_listings(
            listings,
            min_price=min_price,
            max_price=max_price,
            min_sqm=min_sqm,
            max_sqm=max_sqm,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_bathrooms=min_bathrooms,
            property_type=property_type,
        )
        ordered = sort_listings(filtered, sort)
        matched = len(ordered)
        page_items = ordered[offset : offset + limit]
        if include_details:
            page_items = await self._enrich_page(page_items)
        elif page_items and min_bathrooms is None:
            page_ids = [item["id"] for item in page_items if item.get("id") is not None]
            try:
                page_summaries = await self.summaries(page_ids)
            except TecnocasaError as exc:
                enrichment_notice = (
                    enrichment_notice
                    or f"Could not enrich listings from the national API: {exc}"
                )
            else:
                page_by_id = {
                    to_int(item.get("id")): normalize_summary(item)
                    for item in page_summaries
                }
                for index, item in enumerate(page_items):
                    enriched = page_by_id.get(to_int(item.get("id")))
                    if not enriched:
                        continue
                    merged = {
                        **item,
                        **{key: value for key, value in enriched.items() if value is not None},
                    }
                    merged["agency_id"] = item.get("agency_id") or enriched.get("agency_id")
                    merged["detail_url"] = item.get("detail_url") or enriched.get("detail_url")
                    page_items[index] = merged

        notices: list[str] = []
        if enrichment_notice:
            notices.append(enrichment_notice)
        if scope == "area":
            notices.append(
                "Area pages on franchise microsites may show a curated subset. "
                "Use search_listings with the district for complete coverage."
            )
        pagination = re.findall(r'href="[^"]*(?:pagina|page)=', page, re.I)
        if pagination:
            notices.append("The microsite page appears paginated; only page 1 was read.")

        return {
            "source_url": target,
            "scope": scope,
            "agency": {
                "id": meta.get("agency_id"),
                "name": meta.get("agency_name"),
                "microsite_url": meta.get("microsite_url"),
                "area_url": meta.get("area_url"),
            },
            "total_on_page": len(cards),
            "matched": matched,
            "returned": len(page_items),
            "offset": offset,
            "limit": limit,
            "notices": notices,
            "listings": page_items,
        }

    # -- Franchise microsite discovery / aggregation ---------------------

    async def _probe_microsite(self, host: str, refresh: bool = False) -> dict[str, Any]:
        """Check whether a numbered franchise subdomain is live.

        A live microsite answers its root either directly (200) or with a
        redirect to its own area page. Deactivated offices redirect to
        www.tecnocasa.it instead.
        """
        now = time.monotonic()
        cached = self._probe_cache.get(host)
        if cached and not refresh and now - cached[0] < cached[1]:
            return cached[2]

        info: dict[str, Any] = {
            "host": host,
            "live": False,
            "status": None,
            "zone": None,
            "zone_url": None,
            "deactivated_to": None,
            "error": None,
        }
        try:
            response = await self._client.get(
                f"https://{host}/",
                follow_redirects=False,
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            info["error"] = type(exc).__name__
            # A DNS blip should not mark an office dead for hours.
            self._probe_cache[host] = (now, 300.0, info)
            return info

        info["status"] = response.status_code
        location = response.headers.get("location") or ""
        if response.status_code == 200:
            info["live"] = True
        elif response.status_code in (301, 302, 307, 308) and location:
            target = urlparse(location)
            if target.netloc == host:
                info["live"] = True
                info["zone_url"] = location
                segments = [part for part in target.path.strip("/").split("/") if part]
                info["zone"] = segments[-1] if segments else None
            else:
                info["deactivated_to"] = location
        self._probe_cache[host] = (now, MICROSITE_PROBE_TTL, info)
        return info

    async def discover_microsites(
        self,
        city: str = "milano",
        max_index: int = DEFAULT_MAX_MICROSITE_INDEX,
        concurrency: int = 8,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Probe `<city><n>.tecnocasa.it` and report which offices are live."""
        city = normalize_text(city) or "milano"
        max_index = max(1, min(int(max_index), 400))
        hosts = [f"{city}{index}.tecnocasa.it" for index in range(1, max_index + 1)]
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def worker(host: str) -> dict[str, Any]:
            async with semaphore:
                return await self._probe_microsite(host, refresh=refresh)

        results = await asyncio.gather(*(worker(host) for host in hosts))
        live = [item for item in results if item["live"]]
        deactivated = [item for item in results if item["deactivated_to"]]
        unreachable = [item for item in results if item["error"]]

        return {
            "city": city,
            "template": MICROSITE_TEMPLATE.format(city=city, index="N"),
            "scanned": len(hosts),
            "live_count": len(live),
            "deactivated_count": len(deactivated),
            "unreachable_count": len(unreachable),
            "live": [
                {
                    "name": item["host"].split(".")[0],
                    "host": item["host"],
                    "url": f"https://{item['host']}/",
                    "zone": item["zone"],
                    "zone_url": item["zone_url"],
                }
                for item in live
            ],
            "deactivated": [
                {"host": item["host"], "redirect": item["deactivated_to"]}
                for item in deactivated
            ],
            "unreachable": [
                {"host": item["host"], "error": item["error"]} for item in unreachable
            ],
        }

    async def _microsite_listing_page(
        self, host: str, contract: str, refresh: bool = False
    ) -> str:
        contract_code = CONTRACT_MAP.get(contract.lower(), contract)
        path = "/immobili-in-vendita" if contract_code == "acquis" else "/immobili-in-affitto"
        url = f"https://{host}{path}"
        key = "microsite:" + url

        async def fetch() -> str:
            last: Any = None
            for attempt in range(2):
                try:
                    response = await self._client.get(
                        url,
                        follow_redirects=False,
                        timeout=httpx.Timeout(20.0, connect=5.0),
                    )
                    if response.status_code == 200 and len(response.text) > 1000:
                        return response.text
                    if response.status_code in (301, 302, 307, 308):
                        raise TecnocasaError(
                            f"Microsite page redirects to {response.headers.get('location')}"
                        )
                    last = TecnocasaError(f"HTTP {response.status_code}")
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last = exc
                if attempt < 1:
                    await asyncio.sleep(1.0)
            raise TecnocasaError(
                f"Microsite unavailable ({url}): {type(last).__name__}: {last}"
            )

        if refresh:
            self._cache.pop(key, None)
        return await self._cached(key, MICROSITE_PAGE_TTL, fetch)

    async def aggregate_listings(
        self,
        *,
        city: str = "milano",
        contract: str = "sale",
        max_index: int = DEFAULT_MAX_MICROSITE_INDEX,
        areas: Sequence[str] | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        min_sqm: int | None = None,
        max_sqm: int | None = None,
        min_rooms: int | None = None,
        max_rooms: int | None = None,
        min_bathrooms: int | None = None,
        property_type: str | None = None,
        agency_id: str | None = None,
        sort: str = "relevance",
        limit: int = 20,
        offset: int = 0,
        concurrency: int = 6,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Read every live franchise microsite and merge their listings.

        This bypasses the national API, which is the only path that can be
        blocked or rate limited. Coverage is the union of the franchises that
        still have a live microsite.
        """
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        contract_code = CONTRACT_MAP.get(contract.lower(), contract)

        discovery = await self.discover_microsites(
            city=city, max_index=max_index, refresh=refresh
        )
        hosts = [item["host"] for item in discovery["live"]]

        semaphore = asyncio.Semaphore(max(1, concurrency))
        pages: dict[str, str] = {}
        failed: list[dict[str, str]] = []

        async def worker(host: str) -> None:
            async with semaphore:
                try:
                    pages[host] = await self._microsite_listing_page(
                        host, contract_code, refresh=refresh
                    )
                except TecnocasaError as exc:
                    failed.append({"host": host, "error": str(exc)})

        if hosts:
            await asyncio.gather(*(worker(host) for host in hosts))

        listings: list[dict[str, Any]] = []
        agencies: dict[str, dict[str, Any]] = {}
        for host, page in pages.items():
            cards, meta = parse_microsite_cards(page, f"https://{host}/")
            if cards:
                agency = parse_microsite_agency(page)
                agency_id_value = next(
                    (card["agency_id"] for card in cards if card.get("agency_id")), None
                )
                agencies[host] = {
                    "id": agency_id_value,
                    "name": agency["name"],
                    "phone": agency["phone"],
                    "email": agency["email"],
                    "microsite_url": f"https://{host}/",
                }
            listings.extend(card_to_listing(card, host) for card in cards)

        deduped = dedupe_listings(listings)
        filtered = filter_listings(
            deduped,
            min_price=min_price,
            max_price=max_price,
            min_sqm=min_sqm,
            max_sqm=max_sqm,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_bathrooms=min_bathrooms,
            property_type=property_type,
            agency_id=agency_id,
            areas=areas,
        )
        ordered = sort_listings(filtered, sort)
        page_items = ordered[offset : offset + limit]
        for item in page_items:
            host = urlparse(item.get("microsite_url") or "").netloc
            item["agency"] = agencies.get(host)

        notices: list[str] = []
        if discovery["deactivated_count"]:
            notices.append(
                f"{discovery['deactivated_count']} franchise microsites are deactivated "
                "(they redirect to www.tecnocasa.it); their listings are not included."
            )
        if failed:
            notices.append(f"{len(failed)} live microsites could not be read.")
        if areas:
            notices.append(
                "Area filter matches the neighbourhood tag published by each agency; "
                "not every district name appears as a tag."
            )

        return {
            "source": "tecnocasa franchise microsites",
            "city": discovery["city"],
            "contract": contract_code,
            "microsites": {
                "scanned": discovery["scanned"],
                "live": discovery["live_count"],
                "deactivated": discovery["deactivated_count"],
                "unreachable": discovery["unreachable_count"],
                "read": len(pages),
                "with_listings": len(agencies),
            },
            "total": len(deduped),
            "matched": len(ordered),
            "returned": len(page_items),
            "offset": offset,
            "limit": limit,
            "notices": notices,
            "agencies": sorted(agencies.values(), key=lambda item: item["name"] or ""),
            "listings": page_items,
        }

    async def get_franchise_agency(self, url: str) -> dict[str, Any]:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        if not parsed.netloc.endswith("tecnocasa.it"):
            raise ValueError("URL must be a tecnocasa.it domain")
        page = await self._get_html(url, ttl=300)
        cards, meta = parse_microsite_cards(page, url)
        if not cards:
            origin = f"{parsed.scheme}://{parsed.netloc}"
            fallback = origin + "/immobili-in-vendita"
            page = await self._get_html(fallback, ttl=300)
            cards, meta = parse_microsite_cards(page, fallback)
        return {
            "agency": {
                "id": meta.get("agency_id"),
                "name": meta.get("agency_name"),
                "microsite_url": meta.get("microsite_url"),
                "area_url": meta.get("area_url"),
            },
            "title": meta.get("title"),
            "listing_ids_on_page": [card["id"] for card in cards if card.get("id") is not None],
            "area_links": meta.get("area_links") or [],
        }
