# Tecnocasa MCP

MCP server for browsing and filtering **Tecnocasa** listings in Italy — the
national portal plus the franchise microsites.

- Read-only, public data
- No API key
- stdio transport
- Designed for OpenCode / Claude Desktop / Cursor

## Why this is not a simple clone of the Idealista wrapper

Tecnocasa is a **franchise network**. Listings belong to local agencies, and
each agency has its own microsite on a subdomain, e.g.:

```
https://milano34.tecnocasa.it/milano/porta-venezia-quadrilatero/
```

The national portal aggregates the same listings and exposes each listing's
franchise metadata (agency ID, name, phone, email, microsite URL, area URL).
This MCP uses that:

- `search_listings` searches the national API across all agencies.
- `get_listing` returns the franchise agency record with the property.
- `search_franchise_area` reads a specific agency/area microsite.
- `get_franchise_agency` identifies the agency behind a microsite URL, so you
  can then filter the national search with `agency_id`.
- `discover_microsites` finds every live franchise office in a city.
- `aggregate_listings` merges all their listings, deduplicated — a full
  fallback for when `www.tecnocasa.it` is unreachable.

## Tools

### `search_locations(query)`

Resolve a free-text place to Tecnocasa IDs. Examples:

```
search_locations("Porta Venezia, Milano")
search_locations("Trastevere, Roma")
search_locations("Milano")
```

Returns district/city candidates with `id`, `city_id`, `province_id`.

### `search_listings(...)`

Search the national portal. Key parameters:

- `location` — free text, e.g. `"Porta Venezia, Milano"`
- `city_id`, `district_ids`, `province` — exact IDs from `search_locations`
- `contract` — `"sale"` or `"rent"`
- `sector` — `"residential"`, `"industrial"`, `"touristic"`
- `min_price`, `max_price` (EUR)
- `min_sqm`, `max_sqm`
- `min_rooms`, `max_rooms`, `min_bathrooms`
- `property_type` — `apartment`, `house`, `garage`, `commercial`, `land`, `room`
- `agency_id` — filter to one franchise
- `sort` — `relevance`, `price_asc`, `price_desc`, `sqm_asc`, `sqm_desc`, `rooms_asc`, `rooms_desc`
- `limit` (max 50), `offset`
- `include_details` — include full descriptions/features for the returned page

Example:

```
search_listings(
  location="Porta Venezia, Milano",
  contract="sale",
  max_price=500000,
  min_sqm=45,
  min_rooms=2,
  sort="price_asc",
)
```

### `get_listing(property_id)`

Full details for one listing: price, size, rooms, bathrooms, floor, elevator,
garden, balcony, garage, air conditioning, energy class, address, coordinates,
images, published date, description, and the franchise agency record.

### `search_franchise_area(url, scope=...)`

Read a specific franchise microsite:

- `scope="area"` — the given area page (e.g. Porta Venezia/Quadrilatero)
- `scope="agency"` — all listings for that agency (`/immobili-in-vendita` or
  `/immobili-in-affitto`)

Supports the same price/size/rooms/type filters and sorting.

### `get_franchise_agency(url)`

Returns the agency ID/name behind a microsite, the canonical area URL, the
listing IDs currently shown, and links to other areas. Use the agency ID with
`search_listings(agency_id=...)` to search that agency across the national
portal.

### `discover_microsites(city="milano", max_index=120)`

Probes `<city><n>.tecnocasa.it` and reports which franchise offices are live,
with their neighbourhood slug (`zone`), the offices that have been deactivated
(they redirect to `www.tecnocasa.it`) and the subdomains that do not exist.
Results are cached in memory for 6 hours.

### `aggregate_listings(city="milano", contract="rent", ...)`

Reads every live franchise microsite and merges the results — the fallback when
the national portal is unreachable. It fetches each agency's
`/immobili-in-affitto` or `/immobili-in-vendita`, deduplicates by listing ID and
attaches the publishing agency (name, phone, email).

```
aggregate_listings(
  city="milano",
  contract="rent",
  areas=["porta venezia", "indipendenza", "monte nero"],
  min_rooms=2, max_rooms=2,
  sort="price_asc",
)
```

`areas` matches the neighbourhood tag each agency publishes on the card
(`Milano, Via Kramer - Porta Venezia` → `Porta Venezia`). Tags are
agency-provided, so not every district name is present; street-level names work
too.

Measured on Milano: 120 subdomains scanned, 72 live, 65 with rentals, ~320
rental cards, deduplicated, in ~25s at concurrency 6.

## Install and run

```sh
cd /Users/francesco/dev/tecnocasa-mcp
uv run python server.py
```

Or install as a package:

```sh
uv pip install -e .
tecnocasa-mcp
```

## OpenCode

Add it as a local MCP server:

```sh
opencode mcp add tecnocasa --global -- \
  uv run --directory /Users/francesco/dev/tecnocasa-mcp python server.py
opencode mcp list
```

Equivalent config:

```jsonc
{
  "mcp": {
    "servers": {
      "tecnocasa": {
        "type": "local",
        "command": [
          "uv", "run", "--directory",
          "/Users/francesco/dev/tecnocasa-mcp",
          "python", "server.py"
        ]
      }
    }
  }
}
```

## Data source and reliability

The server uses the public JSON endpoints behind `https://www.tecnocasa.it`:

- `/api/geo/autocomplete`
- `/api/estates/search` — the portal's own listing endpoint; returns
  normalised summaries with server-side filtering, sorting and pagination
- `/api/estates/search-by-ids` — exact-ID lookups and `get_listing`

The site has an aggressive WAF and is intermittently slow/502. The client:

- sends browser-like headers over HTTP/2
- keeps a small bounded concurrency (3 API requests, 5 page fetches) instead of
  serialising every call
- uses short attempts (6s API, 10s HTML) with jittered retries, so a stalled
  request fails fast instead of blocking for a minute
- fetches detail pages for `include_details` in parallel with a 35s page budget
- caches autocomplete (24h), searches (10min), summaries (30min, per listing),
  details (1h), and serves a stale value immediately while refreshing it
- coalesces concurrent identical requests into one upstream call
- enters a 20s cooldown after repeated timeouts, instead of hammering the site

### When `www.tecnocasa.it` is unreachable

On some networks the **national host blackholes requests entirely**: TCP and TLS
complete in ~0.1s, then the server returns zero bytes until the timeout — for
every path, with any User-Agent, over HTTP/1.1 or HTTP/2, and even with a real
Chrome TLS fingerprint. Port 80 answers normally (308), and the franchise
microsites on the same IP answer in ~0.3s, so this is a host-scoped edge rule,
not rate limiting.

In that case `search_listings`, `search_locations` and `get_listing` cannot work;
use `aggregate_listings` or `search_franchise_area`, which read the microsites
directly. The client tracks the 20s cooldown so you don't hammer a host that
will never answer.

Franchise **area pages** (`/milano/<zona>/`) are sale-only: requesting
`contract="rent"` there returns sale cards. Use `scope="agency"` or
`aggregate_listings` for rentals.

## Notes / limitations

- Franchise **area pages** may show a curated subset. Use `search_listings`
  with the matching district for complete coverage.
- `aggregate_listings` only sees offices whose microsite is still live; in
  Milano 32 of 104 numbered offices are deactivated and redirect to the national
  portal.
- Microsite cards carry price, size, rooms, bathrooms and the neighbourhood tag
  but not the full description, floor or coordinates. Use the listing
  `detail_url` for those.
- Price, size, rooms, agency, district and sort filters run server-side.
  Bathroom and property-type filters are applied to the returned page (the
  latter is keyword based), so their `matched` count is an estimate.
- `limit` is capped at 50; the search endpoint is fetched with at most 200 rows
  per call, so very deep `offset` values are not supported.
- No writes, no authentication, no personal data.
- Respect Tecnocasa's terms and do not hammer the site; caching and backoff are
  built in for personal use.

## Development

```sh
cd /Users/francesco/dev/tecnocasa-mcp
uv run python -m unittest discover -s tests -v
```
