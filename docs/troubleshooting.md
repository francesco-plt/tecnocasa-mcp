# Troubleshooting

First, check the basics:

```sh
uvx tecnocasa-mcp --version    # prints the version, then exits
```

If that fails, the problem is installation, not MCP. If it works, the server is
fine and the issue is client configuration or upstream availability.

## The client does not list any tools

- Use an **absolute path** to `uvx`/`tecnocasa-mcp` in the client config. GUI
  apps often do not inherit your shell `PATH`.
- Find it with `which uvx` and put that path in `"command"`.
- Restart the client fully, not just the window.
- Validate the JSON: no trailing commas, no comments in `.json` files
  (`.jsonc` and `.vscode/mcp.json` allow comments; most clients do not).
- Check the key name: Claude/Cursor/Windsurf use `mcpServers`, VS Code uses
  `servers`, OpenCode uses `mcp.servers`.
- Look at the client's MCP logs (Claude Desktop: `~/Library/Logs/Claude/`,
  Cursor: Output → MCP).

## `uvx: command not found`

Install uv, then reopen the terminal:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`.

Alternatively use `pipx install tecnocasa-mcp` and point the client at
`tecnocasa-mcp`.

## Requests time out or return 502

The upstream site is behind a WAF and is intermittently slow. This is expected
and the client retries with backoff. Things to try:

- Retry in a minute; searches are cached, so a repeat is often instant.
- Lower `limit` and drop `include_details` — detail pages are the slow part.
- Use `search_franchise_area` or `aggregate_listings`, which read the franchise
  microsites (a different application) instead of `www.tecnocasa.it`.
- Check whether `https://www.tecnocasa.it` loads in a browser on the same
  network.

The server enters a 20 s cooldown after repeated timeouts rather than hammering
the site. A burst of errors followed by a recovery is normal.

## `www.tecnocasa.it` never answers on my network

On some networks the host blackholes requests: TCP and TLS complete in ~0.1 s,
then zero bytes until timeout — every path, any User-Agent, HTTP/1.1 or HTTP/2,
even with a real Chrome TLS fingerprint. Port 80 answers normally (308) and the
franchise microsites on the same IP respond in ~0.3 s, so it is a host-scoped
edge rule, not rate limiting.

This affects `search_listings`, `search_locations` and `get_listing`. Use:

- `aggregate_listings(city="milano", contract="rent", ...)`
- `search_franchise_area(url=..., scope="agency")`
- `discover_microsites(city=...)` to find live offices

Workarounds outside the server: a different network, a VPN, or a DNS/proxy
setup that routes `www.tecnocasa.it` differently.

## A tool returns no results

- Call `search_locations` first and pass `district_ids`/`city_id` rather than
  free text; ambiguous names resolve to the wrong city.
- Check the contract: franchise **area pages are sale-only**. For rentals use
  `scope="agency"` or `aggregate_listings`.
- `areas` in `aggregate_listings` matches agency-provided tags, which may not
  contain every district name. Try a street name.
- Filters combine with AND. Relax `min_rooms`/`max_sqm` before assuming a bug.
- A district can genuinely be empty; widen to the city.

## Results look incomplete

- Franchise area pages are curated subsets. `search_listings` with the district
  is the complete view on the national portal.
- `aggregate_listings` only sees microsites that are still live. In Milano, 32
  of 104 numbered offices are deactivated and redirect to the national portal.
- Deep `offset` values are not supported: `limit` is capped at 50 and the API
  returns at most 200 rows per call.
- Bathroom and property-type filters are applied to the returned page, not
  server-side, so `matched` is an estimate.

## SSL / proxy / corporate network

The client uses `httpx` with HTTP/2. Behind a TLS-inspecting proxy you may need
`SSL_CERT_FILE` or `REQUESTS_CA_BUNDLE` pointing at your corporate CA. The
server does not disable certificate verification, by design.

## Python version

Requires Python 3.10+. `uvx` manages its own interpreter; with `pip` make sure
`python --version` is new enough.

## Enabling debug logs

The server logs to **stderr** (stdout is the MCP transport). Most clients expose
stderr in their MCP log panel. For a manual run:

```sh
uv run --directory /path/to/tecnocasa-mcp python -m tecnocasa_mcp 2>server.log
```

`httpx`/`httpcore` request logging is intentionally suppressed; it would flood
stderr during `aggregate_listings`.

## Still stuck?

Open an issue with the version, client, tool name and sanitized logs:
[github.com/francesco-plt/tecnocasa-mcp/issues](https://github.com/francesco-plt/tecnocasa-mcp/issues).
