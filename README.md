<p align="center">
  <img src="https://raw.githubusercontent.com/francesco-plt/tecnocasa-mcp/main/assets/banner.svg" alt="tecnocasa MCP — real-estate listings across Italy" width="100%">
</p>

<p align="center">
  <a href="https://github.com/francesco-plt/tecnocasa-mcp/actions/workflows/ci.yml"><img src="https://github.com/francesco-plt/tecnocasa-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/tecnocasa-mcp/"><img src="https://img.shields.io/pypi/v/tecnocasa-mcp.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/tecnocasa-mcp/"><img src="https://img.shields.io/pypi/pyversions/tecnocasa-mcp.svg" alt="Python versions"></a>
  <a href="https://github.com/francesco-plt/tecnocasa-mcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/francesco-plt/tecnocasa-mcp/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-keep--a--changelog-orange.svg" alt="Changelog"></a>
</p>

<p align="center">
  <b>English</b> · <a href="https://github.com/francesco-plt/tecnocasa-mcp/blob/main/README.it.md">Italiano</a>
</p>

<!-- mcp-name: io.github.francesco-plt/tecnocasa-mcp -->

**Ask your assistant for Tecnocasa listings anywhere in Italy — sales, rentals,
prices, sizes, rooms and the local franchise agency that publishes each one.**
No API key, no account, read-only, stdio transport.

Works with Claude Code, Claude Desktop, Cursor, VS Code, OpenCode and any other
MCP client.

## Quick start

```sh
uvx tecnocasa-mcp
```

That is the whole install. Register it with your client:

**Claude Code**

```sh
claude mcp add tecnocasa -- uvx tecnocasa-mcp
```

**Claude Desktop / Cursor / Windsurf** — add to the client's MCP config:

```json
{
  "mcpServers": {
    "tecnocasa": {
      "command": "uvx",
      "args": ["tecnocasa-mcp"]
    }
  }
}
```

**VS Code** — `.vscode/mcp.json`:

```json
{
  "servers": {
    "tecnocasa": {
      "type": "stdio",
      "command": "uvx",
      "args": ["tecnocasa-mcp"]
    }
  }
}
```

**OpenCode** — `opencode.jsonc`:

```jsonc
{
  "mcp": {
    "servers": {
      "tecnocasa": {
        "type": "local",
        "command": ["uvx", "tecnocasa-mcp"]
      }
    }
  }
}
```

Per-client file locations, pip/pipx/Docker installs and troubleshooting live in
[docs/clients.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/docs/clients.md).

## What you can ask

> *"Find me two-room rentals in Porta Venezia, Milano, under €1,500 a month,
> cheapest first."*

> *"Which Tecnocasa agencies are active in Torino, and how many listings does
> each have right now?"*

> *"Compare sale prices per square metre in Trastevere and Prati for apartments
> between 60 and 100 m²."*

> *"The national portal is timing out — scan the Milano franchise microsites
> and show me every rental with a balcony under €1,200."*

The assistant picks the right tool. A typical exchange looks like:

```text
you  ▸ cheapest 2-room rental in Porta Venezia, Milano
mcp  ▸ search_locations("Porta Venezia, Milano")
mcp  ▸ search_listings(district_ids=[...], contract="rent",
                       min_rooms=2, max_rooms=2, sort="price_asc")
     ▸ 14 matches · €1,150/mo · 55 m² · Via Kramer · agency: Micc (milano59)
```

## Tools

| Tool | What it does |
|---|---|
| `search_locations` | Resolve free text to Tecnocasa city/district/province IDs |
| `search_listings` | Search the national portal with server-side filters and sorting |
| `get_listing` | Full details for one listing, including its franchise agency |
| `search_franchise_area` | Read a specific agency's microsite (area or whole agency) |
| `get_franchise_agency` | Identify the agency behind a microsite URL |
| `discover_microsites` | Find every live franchise office in a city |
| `aggregate_listings` | Merge all live microsites, de-duplicated — fallback when the portal is down |

Full parameters and return shapes: [docs/tools.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/docs/tools.md).

## How it works

Tecnocasa is a **franchise network**: listings belong to local agencies, and
each agency runs its own numbered microsite, e.g.
`https://milano34.tecnocasa.it/milano/porta-venezia-quadrilatero/`.

The national portal aggregates the same listings and exposes each listing's
franchise metadata (agency ID, name, phone, email, microsite and area URLs).
This server uses both sides:

- `search_listings` queries the national API across all agencies.
- `get_listing` returns the franchise agency record with the property.
- `search_franchise_area` reads one agency/area microsite directly.
- `get_franchise_agency` maps a microsite to an agency ID, so the national
  search can be filtered with `agency_id`.
- `discover_microsites` probes every numbered subdomain for a city.
- `aggregate_listings` merges all live microsites and de-duplicates by listing
  ID — a complete fallback when `www.tecnocasa.it` is unreachable.

Measured on Milano: 120 subdomains scanned, 72 live, 65 with rentals, ~320
rental cards after de-duplication, in ~25 s at concurrency 6.

## Reliability

The public endpoints sit behind an aggressive WAF and are intermittently slow
or return 502. The client is built for that:

- browser-like headers over HTTP/2
- bounded concurrency (3 API requests, 5 page fetches) instead of serial calls
- short attempts (6 s API, 10 s HTML) with jittered retries, so a stalled
  request fails fast
- parallel detail fetches with a 35 s page budget
- caches: autocomplete 24 h, searches 10 min, summaries 30 min, details 1 h
- stale-while-revalidate: a cached value is served immediately while it
  refreshes in the background
- identical concurrent requests are coalesced into one upstream call
- 20 s cooldown after repeated timeouts

### When `www.tecnocasa.it` is unreachable

On some networks the national host blackholes requests: TCP and TLS complete in
~0.1 s, then the server returns zero bytes until timeout — for every path, with
any User-Agent, over HTTP/1.1 or HTTP/2, and with a real Chrome TLS
fingerprint. Port 80 answers normally (308) and the franchise microsites on the
same IP answer in ~0.3 s, so it is a host-scoped edge rule, not rate limiting.

In that case `search_listings`, `search_locations` and `get_listing` cannot
work. Use `aggregate_listings` or `search_franchise_area`, which read the
microsites directly. See [docs/troubleshooting.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/docs/troubleshooting.md).

## Limitations

- Franchise area pages may show a curated subset. Use `search_listings` with
  the matching district for complete coverage.
- `aggregate_listings` only sees offices whose microsite is still live; in
  Milano, 32 of 104 numbered offices are deactivated.
- Microsite cards carry price, size, rooms, bathrooms and the neighbourhood tag,
  but not the full description, floor or coordinates. Use the listing's
  `detail_url` for those.
- Price, size, rooms, agency, district and sort filters run server-side.
  Bathroom and property-type filters are applied to the returned page, so their
  `matched` count is an estimate.
- `limit` is capped at 50 and the search endpoint returns at most 200 rows per
  call, so very deep `offset` values are not supported.
- Franchise area pages are sale-only; use `scope="agency"` or
  `aggregate_listings` for rentals.
- No writes, no authentication, no personal data.

## Development

```sh
git clone https://github.com/francesco-plt/tecnocasa-mcp
cd tecnocasa-mcp
uv sync
uv run python -m unittest discover -s tests -v
uv run ruff check . && uv run ruff format --check .
```

See [CONTRIBUTING.md](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/CONTRIBUTING.md). The test suite is fully mocked and runs
offline in under a second.

## Disclaimer

This project is **not affiliated with, endorsed by, or supported by
Tecnocasa**. It reads publicly available listing pages for personal,
informational use. Respect Tecnocasa's terms of service: caching, bounded
concurrency and backoff are built in — do not raise them. Listing data belongs
to Tecnocasa and the individual franchise agencies.

## License

[MIT](https://github.com/francesco-plt/tecnocasa-mcp/blob/main/LICENSE)
