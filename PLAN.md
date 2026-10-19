# Tecnocasa MCP — Accessibility & Growth Plan

Working document for maintainers. Phases 0–6 are applied in the initial
release; Phase 7 has its own step-by-step guide in
[docs/DISTRIBUTION.md](docs/DISTRIBUTION.md).

**Goal:** anyone can install and run this in under 60 seconds without reading source, the repo looks maintained, and it is discoverable wherever people look for MCP servers.

**Success metrics (90 days):**

- `uvx tecnocasa-mcp` works from a clean machine
- ≤ 3 copy-paste steps for each supported client
- listed in ≥ 4 MCP registries
- CI green on 3 Python versions
- issues get a response; PRs have a path to merge

**Non-goals:** hosted/SaaS version, authentication, write operations, scraping more aggressively.

---

## Ordering constraints (read before starting)

Three items are order-sensitive. Everything else is independent.

1. **Restructure the package before the first PyPI release.** Moving `server.py`/`tecnocasa.py` into `src/tecnocasa_mcp/` after publishing is a breaking change for every user. Do it once, now, while there are no users.
2. **LICENSE before release.** PyPI metadata and the GitHub sidebar both read it; retrofitting means a metadata edit and a re-upload.
3. **Tag `v0.1.0` last**, after packaging, CI, and the README are done — the first release should not be a draft you immediately follow with `v0.1.1`.

`tecnocasa-mcp` is currently free on PyPI (verified: 404). Reserve it early.

---

## Phase 0 — Prep (10 min)

- [ ] Create a branch: `git switch -c chore/oss-readiness`
- [ ] Decide the public identity: author name/email in `pyproject.toml`, `Copyright (c) 2026 <name>`
- [ ] Decide whether the repo stays `tecnocasa-mcp` (recommended: yes, matches the command name)
- [ ] Enable GitHub Issues + Discussions
- [ ] Set repo description: `MCP server for browsing Tecnocasa listings across Italy — national portal + franchise microsites. No API key.`

**Exit:** branch exists, decisions written down in the PR description.

---

## Phase 1 — Legal + package metadata (30 min)

### 1.1 `LICENSE`
- [ ] Add MIT text, `Copyright (c) 2026 Francesco Pallotta`
- [ ] Confirm GitHub detects it ("MIT license" in the sidebar)

### 1.2 `pyproject.toml`
- [ ] `license = "MIT"` + `license-files = ["LICENSE"]` (PEP 639; the current `{ text = "MIT" }` form is deprecated)
- [ ] Add `[project.urls]`: `Homepage`, `Repository`, `Issues`, `Changelog`
- [ ] Add `classifiers`: Development Status 4 – Beta, Intended Audience Developers, License MIT, Programming Language Python 3.10–3.13, Topic Software Development :: ... , Environment Console
- [ ] Add `[dependency-groups] dev = ["ruff>=0.9", "pytest>=8"]`
- [ ] Add `[tool.ruff]` config (`line-length = 88`, `target-version = "py310"`, select `E,F,I,UP,B`)
- [ ] Set `dynamic = ["version"]` + `[tool.hatch.version] path = "src/tecnocasa_mcp/__init__.py"` (single source of truth)

**Exit:** `uv build` succeeds; `twine check dist/*` (or `uvx twine check`) passes; wheel metadata shows license + URLs.

---

## Phase 2 — Package restructure (1–2 h)

This is the highest-risk phase; do it alone in one commit so it is easy to revert.

### 2.1 Layout

```
src/tecnocasa_mcp/
    __init__.py        # __version__ = "0.1.0", public re-exports
    __main__.py        # enables `python -m tecnocasa_mcp`
    server.py          # moved from ./server.py (FastMCP tools)
    client.py          # moved from ./tecnocasa.py
    _parsing.py        # optional: split the pure parsing helpers out of client.py
```

- [ ] Move files; keep `client.py` as one module first (a 1,860-line file is fine; splitting is a separate, later refactor)
- [ ] Update imports: `from tecnocasa import ...` → `from .client import ...`
- [ ] Update `tests/*.py` imports to `from tecnocasa_mcp.client import ...`
- [ ] Add `src/tecnocasa_mcp/__main__.py` that calls `server.main()`
- [ ] Add `--version` handling in `server.main()`/`__main__.py`
- [ ] `[project.scripts] tecnocasa-mcp = "tecnocasa_mcp.server:main"`
- [ ] `[tool.hatch.build.targets.wheel] packages = ["src/tecnocasa_mcp"]`
- [ ] Add `py.typed` marker + `[project]` typing classifier if you want to advertise types
- [ ] Delete stale `__pycache__/` and `.ruff_cache/` from the working tree

### 2.2 Verify

- [ ] `uv run python -m unittest discover -s tests -v` → 25 passing
- [ ] `uv build` → wheel contains only `tecnocasa_mcp/*`
- [ ] `uvx --from dist/*.whl tecnocasa-mcp --version` in a temp dir
- [ ] `uvx --from . tecnocasa-mcp` from the repo (smoke test that stdio starts and waits)
- [ ] `python -m tecnocasa_mcp --version`

**Exit:** clean wheel, no top-level `server`/`tecnocasa` modules, tests green.

> Why this matters: `server.py` as a top-level module collides with other packages on install, and `tecnocasa` is already taken on PyPI — shipping it as a bare import is a namespace hazard.

---

## Phase 3 — Install paths (30 min)

- [ ] Add a `Dockerfile` (python:3.13-slim, `uv sync --frozen --no-dev`, `ENTRYPOINT ["tecnocasa-mcp"]`)
- [ ] Add `.dockerignore`
- [ ] Document the install matrix in the README:

| Method | Command |
|---|---|
| Zero-install | `uvx tecnocasa-mcp` |
| pipx | `pipx install tecnocasa-mcp` |
| pip | `pip install tecnocasa-mcp` |
| Clone | `uv run --directory /path/to/tecnocasa-mcp python -m tecnocasa_mcp` |
| Git, no PyPI | `uvx --from git+https://github.com/francesco-plt/tecnocasa-mcp tecnocasa-mcp` |
| Docker | `docker run -i --rm tecnocasa-mcp` |

- [ ] Replace **every** absolute `/Users/francesco/dev/...` path (README lines ~135, ~152, ~237)

**Exit:** grep for `francesco/dev` returns nothing in tracked files.

---

## Phase 4 — README rewrite (2–3 h, mostly editing)

### 4.1 New structure (above the fold first)

1. Banner image + badge row
2. One-sentence pitch: *"Ask your AI assistant for Tecnocasa listings anywhere in Italy. No API key."*
3. Demo GIF (see Phase 4.3)
4. Install: 3 tabs — Claude Code / Cursor / OpenCode — plus a `claude mcp add` one-liner
5. Five example prompts
6. Feature/tool table (names + one line each) → link to `docs/tools.md`
7. How it works (franchise model, national API + microsites)
8. Reliability & caching
9. Limitations
10. Disclaimer (not affiliated with Tecnocasa)
11. Contributing / License

### 4.2 Asset + badge work

- [ ] `assets/banner.svg` — 1280×320, repo name + tagline + Italian flag/accent. Commit the source SVG, not just PNG.
- [ ] `assets/social-preview.png` — 1280×640, uploaded in GitHub Settings → Social preview (not committed)
- [ ] Badges: CI, PyPI version, Python versions, license, MCP registry
- [ ] `docs/tools.md` — move the full tool reference + parameter tables out of the README
- [ ] `docs/clients.md` — exact config per client: Claude Code, Claude Desktop, Cursor, VS Code, OpenCode, Windsurf
- [ ] `docs/troubleshooting.md` — WAF blocking, 502s, `www.tecnocasa.it` host blackhole, HTTP/2, proxy/VPN
- [ ] `README.it.md` + language switcher line at the top of both files
- [ ] Add a TOC after the badges

### 4.3 Demo asset (needs you, see Phase 8)

- [ ] Record a 15–25 s screen capture of a real query
- [ ] Export GIF ≤ 5 MB (or MP4 + poster, linked)
- [ ] Place immediately under the pitch

**Exit:** a reader who has never heard of Tecnocasa can install and ask a question without scrolling past the fold; no tool parameters in the main README.

---

## Phase 5 — CI + releases (1 h)

### 5.1 `.github/workflows/ci.yml`

```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix: { python-version: ["3.10", "3.11", "3.12", "3.13"] }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run python -m unittest discover -s tests -v
      - run: uv build
      - run: uvx twine check dist/*        # metadata sanity
```

- [ ] Add `concurrency` group to cancel superseded runs
- [ ] Add a `publish` job on `tags: ["v*"]` using **PyPI Trusted Publishing** (OIDC, no token):
  - `permissions: { id-token: write, contents: write }`
  - `uv build` → `uv publish --trusted-publishing always`
  - `gh release create "$TAG" dist/* --generate-notes`
- [ ] Add `dependabot.yml` (pip + github-actions, weekly)

### 5.2 Versioning + changelog

- [ ] `CHANGELOG.md` in Keep a Changelog format, `[Unreleased]` section
- [ ] Tag `v0.1.0` after everything else is merged
- [ ] Draft release notes grouped: Added / Fixed / Known issues
- [ ] (Optional) `release-please` for automated changelog + version PRs

### 5.3 Repository hardening

- [ ] Branch protection on `main`: require CI, require PR review
- [ ] Enable secret scanning + Dependabot alerts
- [ ] Add `SECURITY.md` with a private reporting address and an explicit scope: upstream blocking/502s are **not** security issues

**Exit:** CI badge green; `v0.1.0` release published with artifacts; package installable from PyPI.

---

## Phase 6 — Community files (1–2 h)

- [ ] `CONTRIBUTING.md`: prerequisites, `uv sync --dev`, run tests, run ruff, run the server locally, how to add a tool (server wrapper + client method + parser test + docs entry), fixture policy (synthetic HTML only — never commit live scraped pages), PR checklist, commit style
- [ ] `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1, contact address in it
- [ ] `.github/ISSUE_TEMPLATE/bug_report.yml` — required fields: client, install method, tool name, sanitized output, `--version`
- [ ] `.github/ISSUE_TEMPLATE/feature_request.yml`
- [ ] `.github/ISSUE_TEMPLATE/config.yml` — link Discussions
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` — what changed, why, tests run, docs touched
- [ ] `.github/CODEOWNERS`
- [ ] `.pre-commit-config.yaml` — ruff check + format, trailing whitespace, end-of-file
- [ ] Label set: `good first issue`, `help wanted`, `bug`, `upstream`, `docs`
- [ ] Seed 3–5 `good first issue` tasks (examples: add `min_floor`, Italian README updates, more city fixtures, Docker example)

**Exit:** a stranger can go from clone to merged PR using only committed docs.

---

## Phase 7 — Distribution & discovery (2–4 h, mostly PRs)

- [ ] GitHub topics: `mcp`, `model-context-protocol`, `mcp-server`, `real-estate`, `italy`, `tecnocasa`, `claude`, `llm-tools`, `python`
- [ ] Homepage field → PyPI page or docs
- [ ] `server.json` for the official MCP Registry; run `mcp-publisher` to publish
- [ ] Smithery listing
- [ ] Glama listing
- [ ] mcp.so submission
- [ ] PulseMCP submission
- [ ] PR to `punkpeye/awesome-mcp-servers` (Real Estate / Databases section)
- [ ] PR to any Italian OSS / real-estate awesome lists
- [ ] Add one-click install badges: `mcp-installer` / Cursor deeplink / VS Code install link
- [ ] Post: r/ClaudeAI, r/mcp, r/ItaliaDeveloper, Hacker News "Show HN" (once, after demo GIF is in)

**Exit:** ≥ 4 registry pages live; all links point to the canonical repo.

---

## Phase 8 — Manual steps only you can do

These are blockers for the phases above; batch them early.

- [ ] Create a PyPI account; enable 2FA
- [ ] Reserve the `tecnocasa-mcp` project name (upload `0.1.0`, or set up a **pending trusted publisher** pointing at `francesco-plt/tecnocasa-mcp` + workflow `ci.yml` + env `pypi`)
- [ ] Add a `pypi` environment in GitHub repo settings (for trusted publishing)
- [ ] Record the demo GIF/screencast
- [ ] Create/commit `assets/banner.svg` (or commission one; a clean typographic SVG beats a busy graphic)
- [ ] Upload the social preview in repo settings
- [ ] GitHub: enable Discussions, set topics, protect `main`
- [ ] Registry accounts (Smithery/Glama/mcp.so/PulseMCP) — some need GitHub OAuth login
- [ ] Decide on attribution wording for the disclaimer

---

## Commit sequence

Each commit is independently reviewable; squash only if you prefer.

1. `chore: add MIT license and package metadata`
2. `refactor: move package into src/tecnocasa_mcp`
3. `build: add Dockerfile and install matrix`
4. `ci: add test, lint and publish workflows`
5. `docs: rewrite README, split tool reference into docs/`
6. `docs: add contributing, code of conduct and issue templates`
7. `chore: add pre-commit, dependabot and repository hardening`
8. `chore(release): v0.1.0`
9. `docs: add registry listings and install badges` (post-release)

---

## Definition of done

- [ ] `LICENSE`, `README.md`, `README.it.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` exist
- [ ] `grep -r "francesco/dev"` on tracked files → no results
- [ ] `uvx tecnocasa-mcp --version` works on a machine that has never seen this repo
- [ ] `uv build` wheel contains only `tecnocasa_mcp/`
- [ ] CI green on 3.10–3.13; badge shows passing
- [ ] `v0.1.0` tagged and published to PyPI with trusted publishing
- [ ] README first screen: banner, badges, pitch, demo, install
- [ ] ≥ 4 registry listings live
- [ ] Issues/Discussions enabled, `main` protected
- [ ] `PLAN.md` deleted or moved out of the repo

---

## Risk notes

| Risk | Mitigation |
|---|---|
| Upstream WAF blocks CI or new users immediately | Keep the microsite fallback prominent in README + troubleshooting; document the host-blackhole behaviour; never let CI hit the network (tests are mocked — keep it that way) |
| Scraping ToS complaints | Read-only, no auth, no personal data, aggressive caching + rate limits already present; add the non-affiliation disclaimer; stay ready to add `robots.txt` respect notes |
| PyPI name squatting | Reserve `0.1.0` in Phase 8, before the README rewrite goes public |
| Restructure breaks tests late | Do Phase 2 alone, verify with a clean-venv `uvx` run |
| Registry listings go stale | Add a quarterly checklist item to the release notes |

## Effort estimate

| Phase | Time |
|---|---|
| 0–1 | 40 min |
| 2 | 1–2 h |
| 3 | 30 min |
| 4 | 2–3 h (+ recording) |
| 5 | 1 h |
| 6 | 1–2 h |
| 7 | 2–4 h |
| **Total** | **~1.5 focused days** |
