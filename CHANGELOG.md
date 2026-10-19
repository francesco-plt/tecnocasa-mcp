# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-19

### Added

- MCP tools: `search_locations`, `search_listings`, `get_listing`,
  `search_franchise_area`, `get_franchise_agency`, `discover_microsites`,
  `aggregate_listings`.
- National portal client with server-side filtering, sorting and pagination.
- Franchise microsite parsing, agency discovery and de-duplicated aggregation
  across every live office in a city.
- Caching (autocomplete, searches, summaries, details), stale-while-revalidate,
  request coalescing and cooldown after repeated upstream timeouts.
- `uvx`, `pip`, `pipx` and Docker entry points; `python -m tecnocasa_mcp`.

[Unreleased]: https://github.com/francesco-plt/tecnocasa-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/francesco-plt/tecnocasa-mcp/releases/tag/v0.1.0
