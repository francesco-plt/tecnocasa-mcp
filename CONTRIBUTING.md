# Contributing

Thanks for taking the time to contribute. This project is a read-only MCP
server over public Tecnocasa data; the most useful contributions are parser
fixes, new filters, better error messages, and documentation.

## Setup

```sh
git clone https://github.com/francesco-plt/tecnocasa-mcp
cd tecnocasa-mcp
uv sync
```

`uv sync` creates `.venv` and installs the package in editable mode, including
the `dev` dependency group (ruff, pytest).

## Development loop

```sh
uv run python -m unittest discover -s tests -v   # 25 tests, fully offline
uv run ruff check .
uv run ruff format .
uv run python -m tecnocasa_mcp                   # run the server over stdio
uv run tecnocasa-mcp --version
```

The tests must never touch the network. All HTTP is injected through a mock
transport; keep it that way so CI stays deterministic and we never hammer the
upstream site from GitHub runners.

## Project layout

```
src/tecnocasa_mcp/
    __init__.py   version and public exports
    __main__.py   python -m entry point
    server.py     FastMCP tool definitions (thin wrappers, docstrings are the API)
    client.py     HTTP client, parsers, normalizers, caching, filters
tests/
    test_client.py    request building, caching, batching, concurrency
    test_parsing.py   HTML/JSON parsing and normalization
```

## Adding or changing a tool

1. Implement the behaviour in `client.py` (pure helpers at module level,
   I/O in `TecnocasaClient`).
2. Expose it in `server.py` as an `@mcp.tool()` with a docstring that states
   what it returns and its limitations — agents read that docstring.
3. Add a test. Parsers and filters get a unit test; new HTTP paths get a
   mocked-transport test.
4. Document it in `docs/tools.md` and, if it is a headline feature, in the
   README.
5. Run `uv run ruff format .` and the full test suite.

## Fixture policy

**Do not commit live scraped pages.** They are large, they contain third-party
content, and they go stale. Build small synthetic HTML/JSON fixtures that
reproduce the structure you need, and keep them inline in the test when
possible.

## Pull requests

- One logical change per PR; keep refactors separate from behaviour changes.
- Include a short "why" in the description, not just a "what".
- State which commands you ran (`unittest`, `ruff`, manual client check).
- Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes.
- Do not bump the version or edit release tags; that happens at release time.

## Commit messages

Conventional Commits are preferred, not required:

```
feat: add min_floor filter
fix: parse prices with non-breaking spaces
docs: document Cursor setup
chore: bump httpx
```

## Upstream etiquette

Tecnocasa's endpoint is a third-party service. Changes that increase request
volume, bypass rate limits, remove caching, or add write/authentication
behaviour will not be merged. Keep concurrency low and backoff in place.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
