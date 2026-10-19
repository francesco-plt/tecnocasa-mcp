# Tool reference

All tools are read-only and return plain JSON. Errors are returned as
`{"error": "...", "retryable": true, "hint": "..."}` instead of raising, so the
assistant can explain the failure or switch tools.

## `search_locations(query)`

Resolve free text to Tecnocasa IDs. Use it first when a district name is
ambiguous, then pass the stable IDs to `search_listings`.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | `"Porta Venezia, Milano"`, `"Trastevere, Roma"`, `"Milano"` |

Returns `query`, `resolved` (the best match) and `candidates` with `type`
(`district` / `city` / `province` / `region`), `id`, `city_id`, `province_id`.

## `search_listings(...)`

Search the national portal across every franchise.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `location` | string | – | Free text, resolved automatically |
| `city_id` | int | – | Exact city ID from `search_locations` |
| `district_ids` | int[] | – | Exact district IDs |
| `province` | string | – | Province code, e.g. `"MI"` |
| `contract` | `"sale"` \| `"rent"` | `"sale"` | |
| `sector` | `"residential"` \| `"industrial"` \| `"touristic"` | `"residential"` | |
| `min_price` / `max_price` | int | – | EUR |
| `min_sqm` / `max_sqm` | int | – | Square metres |
| `min_rooms` / `max_rooms` | int | – | Rooms (locali) |
| `min_bathrooms` | int | – | Applied after the server response |
| `property_type` | string | – | `apartment`, `house`, `garage`, `commercial`, `land`, `room` |
| `agency_id` | string | – | Filter to one franchise, e.g. `"micc4"` |
| `sort` | enum | `"relevance"` | `price_asc`, `price_desc`, `sqm_asc`, `sqm_desc`, `rooms_asc`, `rooms_desc` |
| `limit` | int | `20` | Capped at 50 |
| `offset` | int | `0` | Shallow pagination only |
| `include_details` | bool | `false` | Enrich the page with full descriptions/features (slower) |

Returns `total_in_area`, `total_matching`, `matched`, `has_more`, `listings`,
`resolved`, `candidates`, `notices`.

```jsonc
{
  "location": "Porta Venezia, Milano",
  "contract": "sale",
  "max_price": 500000,
  "min_sqm": 45,
  "min_rooms": 2,
  "sort": "price_asc"
}
```

## `get_listing(property_id, include_description=True)`

Full details for one listing: price, size, rooms, bathrooms, floor, elevator,
garden, balcony, garage, air conditioning, energy class, address, coordinates,
images, published date, description, and the franchise agency record (name,
phone, email, microsite URL, area URL).

Set `include_description=false` to trim long HTML from the response.

## `search_franchise_area(url, ...)`

Read a specific franchise microsite.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | string | – | e.g. `https://milano34.tecnocasa.it/milano/porta-venezia-quadrilatero/` |
| `scope` | `"area"` \| `"agency"` | `"area"` | Area page, or all listings for the agency |
| `contract` | `"sale"` \| `"rent"` | `"sale"` | Ignored for area pages, which are sale-only |

Accepts the same `min_price`, `max_price`, `min_sqm`, `max_sqm`, `min_rooms`,
`max_rooms`, `min_bathrooms`, `property_type`, `sort`, `limit`, `offset`,
`include_details` as `search_listings`.

Results are enriched from the national API and include the agency name and ID.

## `get_franchise_agency(url)`

Identify the agency behind a microsite URL. Returns the agency ID, name,
microsite URL, canonical area URL, listing IDs currently shown, and links to
other area pages.

Use the agency ID with `search_listings(agency_id=...)` to search all of that
agency's listings on the national portal.

## `discover_microsites(city="milano", max_index=120, refresh=False)`

Probe `<city><n>.tecnocasa.it` and report which offices are live, with their
neighbourhood slug. Also lists deactivated offices (they redirect to
`www.tecnocasa.it`) and subdomains that do not exist. Cached in memory for
6 hours; `refresh=true` re-probes.

## `aggregate_listings(city="milano", contract="rent", ...)`

Read every live franchise microsite in a city and merge the results — the
fallback when the national portal is unreachable.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `city` | string | `"milano"` | Subdomain prefix, lowercase |
| `contract` | `"sale"` \| `"rent"` | `"rent"` | |
| `max_index` | int | `120` | Highest franchise number to probe |
| `areas` | string[] | – | Neighbourhood keywords matched against each card's location tag |
| `concurrency` | int | `6` | Parallel microsite fetches; keep it polite |
| `refresh` | bool | `false` | Bypass caches and re-scan |

Accepts the same price/size/rooms/bathrooms/type/agency/sort/limit/offset
parameters as `search_listings`.

`areas` matches the tag each agency publishes on the card
(`Milano, Via Kramer - Porta Venezia` → `Porta Venezia`). Tags are
agency-provided, so not every district name is present; street-level names
work too.

Returns aggregate counters (microsites scanned/live/read, total, matched), the
page of listings and the contributing agencies.

```jsonc
{
  "city": "milano",
  "contract": "rent",
  "areas": ["porta venezia", "indipendenza", "monte nero"],
  "min_rooms": 2,
  "max_rooms": 2,
  "sort": "price_asc"
}
```
