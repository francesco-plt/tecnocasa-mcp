"""Tecnocasa MCP server.

Public, read-only access to Tecnocasa listings across Italy, including the
franchise microsites. No API key required.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

from mcp.server.fastmcp import FastMCP

from . import __version__
from .client import TecnocasaClient, TecnocasaError

# FastMCP configures INFO logging; httpx then logs every request, which floods
# the client's stderr for aggregate_listings (100+ requests).
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

mcp = FastMCP("tecnocasa")
client = TecnocasaClient()


def _error(exc: Exception) -> dict:
    return {
        "error": str(exc),
        "retryable": isinstance(exc, TecnocasaError),
        "hint": (
            "If the national portal is unreachable, use `aggregate_listings` or "
            "`search_franchise_area`, which read the franchise microsites directly."
        ),
    }


@mcp.tool()
async def search_locations(query: str) -> dict:
    """Resolve a free-text place to Tecnocasa location IDs.

    Use this first when a neighborhood name is ambiguous. Examples:
    "Porta Venezia, Milano", "Trastevere, Roma", "Milano", "Torino".
    Returns candidates with `type` (district/city/province/region), `id`,
    `city_id` and `province_id`. Pass `district_ids`/`city_id`/`province` to
    `search_listings` for exact control.
    """
    try:
        resolution = await client.resolve_location(query)
        return {
            "query": query,
            "resolved": resolution["resolved"],
            "candidates": resolution["candidates"],
        }
    except Exception as exc:  # noqa: BLE001 - surface a useful MCP result
        return _error(exc)


@mcp.tool()
async def search_listings(
    location: str | None = None,
    city_id: int | None = None,
    district_ids: list[int] | None = None,
    province: str | None = None,
    contract: Literal["sale", "rent"] = "sale",
    sector: Literal["residential", "industrial", "touristic"] = "residential",
    min_price: int | None = None,
    max_price: int | None = None,
    min_sqm: int | None = None,
    max_sqm: int | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    min_bathrooms: int | None = None,
    property_type: str | None = None,
    agency_id: str | None = None,
    sort: Literal[
        "relevance",
        "price_asc",
        "price_desc",
        "sqm_asc",
        "sqm_desc",
        "rooms_asc",
        "rooms_desc",
    ] = "relevance",
    limit: int = 20,
    offset: int = 0,
    include_details: bool = False,
) -> dict:
    """Search Tecnocasa listings across Italy.

    Tecnocasa is a franchise: every result includes the agency ID. Use
    `get_listing` for the agency name, phone, microsite and full description.

    Args:
        location: Free text, e.g. "Porta Venezia, Milano" or "Milano".
        city_id/district_ids/province: Exact IDs from `search_locations`.
        contract: "sale" or "rent".
        sector: "residential", "industrial" or "touristic".
        min_price/max_price: EUR.
        min_sqm/max_sqm: Square metres.
        min_rooms/max_rooms: Number of rooms (locali).
        min_bathrooms: Minimum bathrooms (applied after the server response).
        property_type: e.g. apartment, house, garage, commercial, land, room.
        agency_id: Filter to one franchise, e.g. "micc4".
        sort: relevance, price_asc, price_desc, sqm_asc, sqm_desc,
            rooms_asc, rooms_desc.
        limit/offset: Pagination; limit is capped at 50.
        include_details: Fetch full description/features for the returned page
            (slower; detail pages are fetched in parallel with a time budget).

    Price, surface, rooms, district, agency and sort filters run server-side;
    only bathrooms and property type are applied locally. Returns total_in_area,
    total_matching, matched, has_more, listings, resolved location, candidates
    and notices.
    """
    try:
        return await client.search_listings(
            location=location,
            city_id=city_id,
            district_ids=district_ids,
            province=province,
            contract=contract,
            sector=sector,
            min_price=min_price,
            max_price=max_price,
            min_sqm=min_sqm,
            max_sqm=max_sqm,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_bathrooms=min_bathrooms,
            property_type=property_type,
            agency_id=agency_id,
            sort=sort,
            limit=limit,
            offset=offset,
            include_details=include_details,
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
async def get_listing(property_id: int, include_description: bool = True) -> dict:
    """Get full details for one Tecnocasa listing.

    Returns price, size, rooms, bathrooms, floor, features (elevator, garden,
    balcony, garage, air conditioning, etc.), energy class, address, map
    coordinates, images, published date and the full franchise agency record
    (name, phone, email, microsite URL and area URL).
    """
    try:
        listing = await client.get_listing(property_id)
        if not include_description:
            listing.pop("description", None)
            listing.pop("description_html", None)
        return listing
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
async def search_franchise_area(
    url: str,
    contract: Literal["sale", "rent"] = "sale",
    scope: Literal["area", "agency"] = "area",
    min_price: int | None = None,
    max_price: int | None = None,
    min_sqm: int | None = None,
    max_sqm: int | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    min_bathrooms: int | None = None,
    property_type: str | None = None,
    sort: Literal[
        "relevance",
        "price_asc",
        "price_desc",
        "sqm_asc",
        "sqm_desc",
        "rooms_asc",
        "rooms_desc",
    ] = "relevance",
    limit: int = 20,
    offset: int = 0,
    include_details: bool = False,
) -> dict:
    """Search a specific Tecnocasa franchise microsite.

    `url` is a franchise page such as
    https://milano34.tecnocasa.it/milano/porta-venezia-quadrilatero/

    scope="area" reads that area page; scope="agency" reads all listings for
    the agency (/immobili-in-vendita or /immobili-in-affitto). Results are
    enriched from the national Tecnocasa API and include the agency name/ID.

    Area pages may show a curated subset; use `search_listings` with the
    district for complete coverage.
    """
    try:
        return await client.search_franchise_area(
            url,
            contract=contract,
            scope=scope,
            min_price=min_price,
            max_price=max_price,
            min_sqm=min_sqm,
            max_sqm=max_sqm,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_bathrooms=min_bathrooms,
            property_type=property_type,
            sort=sort,
            limit=limit,
            offset=offset,
            include_details=include_details,
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
async def discover_microsites(
    city: str = "milano",
    max_index: int = 120,
    refresh: bool = False,
) -> dict:
    """List the live Tecnocasa franchise microsites for a city.

    Franchise microsites are numbered subdomains (`milano1..milanoN`) served by
    a different application than www.tecnocasa.it, so they usually stay
    reachable when the national portal does not.

    Args:
        city: Subdomain prefix, e.g. "milano", "roma", "torino" (lowercase).
        max_index: Highest subdomain number to probe (default 120).
        refresh: Ignore the 6-hour probe cache and re-check every host.

    Returns live hosts with their zone slug, plus deactivated offices (they
    redirect to www.tecnocasa.it) and unreachable hosts.
    """
    try:
        return await client.discover_microsites(
            city=city, max_index=max_index, refresh=refresh
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
async def aggregate_listings(
    city: str = "milano",
    contract: Literal["sale", "rent"] = "rent",
    max_index: int = 120,
    areas: list[str] | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_sqm: int | None = None,
    max_sqm: int | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    min_bathrooms: int | None = None,
    property_type: str | None = None,
    agency_id: str | None = None,
    sort: Literal[
        "relevance",
        "price_asc",
        "price_desc",
        "sqm_asc",
        "sqm_desc",
        "rooms_asc",
        "rooms_desc",
    ] = "relevance",
    limit: int = 20,
    offset: int = 0,
    concurrency: int = 6,
    refresh: bool = False,
) -> dict:
    """Search every live franchise microsite in a city and merge the results.

    This is the fallback when the national portal (`search_listings`) is
    unreachable: it reads each agency's `/immobili-in-affitto` or
    `/immobili-in-vendita` page, deduplicates by listing ID and returns the
    union, with the publishing agency's name, phone and email.

    Args:
        city: Subdomain prefix, e.g. "milano" (lowercase).
        contract: "sale" or "rent".
        max_index: Highest franchise number to probe (default 120).
        areas: Neighbourhood keywords matched against each card's location tag
            (e.g. ["porta venezia", "indipendenza", "monte nero"]). Tags come
            from the agency, so not every district name is present.
        min_price/max_price: EUR.
        min_sqm/max_sqm: Square metres.
        min_rooms/max_rooms: Number of rooms (locali).
        min_bathrooms: Minimum bathrooms.
        property_type: apartment, house, garage, commercial, land, room.
        agency_id: Filter to one franchise, e.g. "micc4".
        sort: relevance, price_asc, price_desc, sqm_asc, sqm_desc,
            rooms_asc, rooms_desc.
        limit/offset: Pagination; limit is capped at 50.
        concurrency: Parallel microsite fetches (default 6; keep it polite).
        refresh: Bypass caches and re-scan.

    Returns aggregate counters (microsites scanned/live/read, total, matched)
    plus the page of listings and the list of contributing agencies.
    """
    try:
        return await client.aggregate_listings(
            city=city,
            contract=contract,
            max_index=max_index,
            areas=areas,
            min_price=min_price,
            max_price=max_price,
            min_sqm=min_sqm,
            max_sqm=max_sqm,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_bathrooms=min_bathrooms,
            property_type=property_type,
            agency_id=agency_id,
            sort=sort,
            limit=limit,
            offset=offset,
            concurrency=concurrency,
            refresh=refresh,
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
async def get_franchise_agency(url: str) -> dict:
    """Identify the franchise agency behind a Tecnocasa microsite URL.

    Returns the agency ID, agency name, microsite URL, canonical area URL,
    listing IDs currently shown, and links to other area pages. Use the agency
    ID with `search_listings(agency_id=...)` to search all of that agency's
    listings across the national portal.
    """
    try:
        return await client.get_franchise_agency(url)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


def main() -> None:
    if "--version" in sys.argv[1:] or "-V" in sys.argv[1:]:
        print(f"tecnocasa-mcp {__version__}")
        return
    mcp.run()


if __name__ == "__main__":
    main()
