# Contributing to tecnocasa-mcp

## Setup

```sh
git clone https://github.com/francesco-plt/tecnocasa-mcp
cd tecnocasa-mcp
uv sync
uv run python -m unittest discover -s tests -v
```

## Before opening a PR

- [ ] Tests pass (`uv run python -m unittest discover -s tests -v`)
- [ ] Lint and format pass (`uv run ruff check . && uv run ruff format --check .`)
- [ ] New behaviour has a test that does not hit the network
- [ ] Docs updated (`docs/tools.md` for tool changes, `CHANGELOG.md` under `[Unreleased]`)
- [ ] No live scraped fixtures committed

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.
