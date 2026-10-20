# Subagent execution plan — Phase 7 prep

Status check (2026-10-20, verified):

- `main` is **9 commits ahead of origin**, working tree clean
- `v0.1.0` exists **locally only**, not pushed
- PyPI `tecnocasa-mcp` → 404 (not published)
- MCP Registry search → 0 results
- `gh` token invalid → no GitHub API automation

## What agents can and cannot do

| Work | Delegate? | Why |
|---|---|---|
| Preflight audit | ✅ `explore` | read-only, local |
| Social preview + demo asset | ✅ `general` | local rendering, headless browser |
| Submission copy pack | ✅ `general` | writing only |
| Release/version tooling | ✅ `general` | local scripts |
| Verification pass | ✅ `explore` | read-only, local |
| PyPI pending publisher | ❌ | needs your login + 2FA |
| `git push` / tag push | ❌ | no credentials |
| GitHub settings | ❌ (semi) | `gh` needs `gh auth login`; topics/description can be scripted afterwards |
| `mcp-publisher login github` | ❌ | device flow in a browser |
| Directory forms (Smithery, Glama, mcp.so, PulseMCP) | ❌ | OAuth/accounts |
| Show HN / Reddit / X posts | ❌ | your identity, one-shot |
| Demo recording | ⚠️ partial | a headless mock can be generated; a real client capture needs your screen |

Do **not** hand an agent your PyPI password, a PyPI token, or an already-authenticated browser session. Nothing in this plan requires it.

---

## Agent roster and file ownership

Parallel agents share the working tree. Ownership is exclusive per path — this is what keeps the merge trivial.

| ID | Agent | Owns (write) | May read |
|---|---|---|---|
| A | `explore` | nothing (report only) | everything |
| B | `general` | `assets/*`, the demo `<img>` line in `README.md` / `README.it.md` | everything |
| C | `general` | `docs/submissions/**` | everything |
| D | `general` | `scripts/**`, `Makefile`, `.github/workflows/ci.yml` | everything |
| E | `explore` | nothing (verification report) | everything |

Rules for every agent:

- **No git commits, no pushes, no tags.** The main thread reviews and commits.
- Stay inside owned paths. If a shared file must change and you do not own it, report the exact patch instead of editing.
- Never invent facts about the project. Read `README.md`, `docs/tools.md` and `server.json` first.
- Do not add runtime dependencies.
- Run `uv run python -m unittest discover -s tests` and `uv run ruff check .` before reporting done.

---

## Wave 0 — Audit (blocking, ~10 min)

Spawn **A** first. Its findings determine whether B/C/D start clean.

Prompt:

> Read-only audit of /Users/francesco/dev/tecnocasa-mcp. Do not modify files.
> Check and report with severity + exact `file:line`:
> 1. Version consistency: `src/tecnocasa_mcp/__init__.py` `__version__`, `server.json` (top-level and `packages[0].version`), `CHANGELOG.md`, and the local `v0.1.0` tag.
> 2. All links in `README.md`, `README.it.md`, `CONTRIBUTING.md`, `docs/*.md` — every referenced local file must exist; flag links still using relative paths that would break on PyPI.
> 3. Tool names and counts consistent across `src/tecnocasa_mcp/server.py`, `docs/tools.md`, `README.md`, `README.it.md` (expected: 7 tools).
> 4. Any absolute `/Users/...` path or stale `server.py` reference in tracked files.
> 5. Every JSON/YAML example in docs parses (copy fenced blocks into a temp file and validate).
> 6. `.gitignore` covers `dist/`, `build/`, `.venv`, caches, `*.egg-info`.
> 7. Run: unit tests, `ruff check`, `ruff format --check`, `uv build`, `uvx twine check dist/*`, and `uvx --from . tecnocasa-mcp --version`.
> 8. Check whether `docker build -t tecnocasa-mcp:audit .` succeeds; if it fails, capture the first error and do not retry more than once.
> Output: a table of findings ordered by severity (blocker / should-fix / nit) with a suggested fix per row. No fixes applied.

Gate: no blockers → start Wave 1. If blockers exist, main thread fixes them first.

---

## Wave 1 — Three builders in parallel (~30–45 min)

### B — Demo + social assets

Deliverables:

- `assets/social-preview.png`, exactly 1280×640, from `assets/banner.svg`
- `assets/demo.gif` (< 5 MB, ≤ 25 s, 12 fps) or `assets/demo.mp4` + `assets/demo-poster.png`
- `assets/demo.html` (source of the mock, committed for reproducibility)
- demo image inserted under the pitch in both READMEs, absolute `raw.githubusercontent.com` URL, descriptive alt text

Prompt:

> You own `assets/**` and the single demo-image line in `/Users/francesco/dev/tecnocasa-mcp/README.md` and `README.it.md`. Do not touch anything else.
> Build two assets:
> 1. `assets/social-preview.png`, 1280×640, rendered from `assets/banner.svg` with padding adjusted for GitHub's social card. Try `rsvg-convert`, then `inkscape`, then `sips`, then Python `cairosvg`; if none is available, render the SVG in a headless Chrome page at 1280×640 and screenshot it.
> 2. An illustrative demo. Create `assets/demo.html`: a neutral, dark, single-column mock of an assistant session (no third-party logos, label it "illustrative example"). Content must reflect the real API: a prompt asking for a 2-room rental in Porta Venezia under €1,500, a `search_listings` call with plausible arguments, and 3 result rows with the real field names (price, size, rooms, area, agency). Animate the reveal with CSS only. Record it with the chrome-devtools screencast tool (start page → screencast_start → wait for the animation → screencast_stop), then convert to GIF with ffmpeg: `ffmpeg -i in.mp4 -vf "fps=12,scale=1000:-1" -loop 0 assets/demo.gif`. If recording is unavailable, export a static `assets/demo.png` instead and say so.
> 3. Insert the result under the pitch paragraph in both READMEs, after the "Works with..." line, using `<img src="https://raw.githubusercontent.com/francesco-plt/tecnocasa-mcp/main/assets/demo.gif" alt="Example session: asking for rentals in Porta Venezia" width="720">`. Keep a `<!-- demo: ... -->` comment noting how to re-record it.
> Constraints: no invented features, no fake prices presented as real listings (use clearly illustrative values), keep the GIF under 5 MB, do not modify badge rows or other README sections.

Acceptance: both files exist, image dimensions/GIF size verified, README diffs are one insertion per file, no other changes.

### C — Submission pack

Deliverables: `docs/submissions/` with one file per channel, ready to paste.

Prompt:

> You own `docs/submissions/**` only. Read `README.md`, `docs/DISTRIBUTION.md`, `docs/tools.md`, `server.json`, `SECURITY.md` first.
> Write a submission pack for Phase 7. Canonical facts: name `tecnocasa-mcp`; one-liner `Browse and filter Tecnocasa real-estate listings across Italy, including franchise microsites.` (≤100 chars); install `uvx tecnocasa-mcp`; repo `https://github.com/francesco-plt/tecnocasa-mcp`; license MIT; 7 tools; read-only; no API key; Python 3.10+; stdio.
> Files:
> - `README.md` — index table: channel, URL, what is needed, time estimate, status checkbox.
> - `01-github-settings.md` — description, website, 9 topics, social preview spec, environment `pypi`, branch protection, plus the exact `gh repo edit` command for when `gh` is authenticated.
> - `02-official-registry.md` — prerequisites, `mcp-publisher` commands, expected output, verification curl, the PyPI ownership `mcp-name` requirement, and the version-bump rule.
> - `03-directories.md` — Glama, Smithery, mcp.so, PulseMCP: URL, category/tags, start command, and the exact copy for each field.
> - `04-awesome-pr.md` — PR title, body, the exact one-line entry with `🐍 🏠`, and a pre-submit checklist.
> - `05-launch.md` — Show HN title + body, Reddit variants for r/mcp, r/ClaudeAI, r/ItaliaDeveloper, one X post ≤ 280 chars, one LinkedIn post. Factual tone, no superlatives, no "revolutionary", no emoji spam. State read-only/no-API-key once, and the franchise-microsite angle once.
> - `06-good-first-issues.md` — 5 issue titles + bodies with labels and acceptance criteria.
> Rules: no fabricated metrics beyond the Milano measurement already in the README (~120 scanned / 72 live / ~320 rental cards / ~25 s). Italian where the audience is Italian. Each launch body must be copy-paste ready, not an outline.

Acceptance: every file exists, character limits respected (Show HN title ≤ 80, X ≤ 280), no placeholders like `TODO`.

### D — Release tooling

Deliverables:

- `scripts/check-versions.py` — reads `src/tecnocasa_mcp/__init__.py` and `server.json`, fails with a clear message on mismatch
- `scripts/preflight.sh` — `set -euo pipefail`; sync, tests, ruff check, ruff format check, build, twine check, version check, clean `uvx --version`
- `Makefile` — `test`, `lint`, `format`, `build`, `preflight`, `release`, `docker`, `clean`
- `.github/workflows/ci.yml` — add a `version-check` step to the `test` job (no new job)
- `scripts/install-links.py` — prints VS Code and Cursor install URLs for `uvx tecnocasa-mcp`, with correct URL-encoding/base64
- `docs/install-links.md` — generated output + how to regenerate

Prompt:

> You own `scripts/**`, `Makefile`, `docs/install-links.md` and exactly one added step inside `.github/workflows/ci.yml`. Do not change other CI jobs or the publish logic.
> Read `pyproject.toml`, the workflow, `server.json` and `CHANGELOG.md` first.
> Build release tooling with no new Python dependencies:
> 1. `scripts/check-versions.py` — stdlib only; compares `__version__` in `src/tecnocasa_mcp/__init__.py` with `server.json` top-level `version` and `packages[0].version`; exits 1 with a precise message listing both values.
> 2. `scripts/preflight.sh` — executable; fails fast; runs the same commands CI runs, plus the version check and `docker build` only if `SKIP_DOCKER` is unset.
> 3. `Makefile` with phony targets and a one-line `help`. `make release VERSION=x.y.z` must: require a clean tree, bump `__version__` and both `server.json` versions, move `[Unreleased]` in `CHANGELOG.md` to the new version with today's date, run preflight, commit `chore(release): vX.Y.Z`, and create an annotated tag. It must never push.
> 4. `scripts/install-links.py` — encodes `{"command":"uvx","args":["tecnocasa-mcp"]}` for VS Code (`urllib.parse.quote`) and Cursor (standard base64 of the exact JSON), prints both URLs and writes `docs/install-links.md`.
> 5. Add `- run: uv run python scripts/check-versions.py` to the existing `test` job after `uv build`.
> Test everything you write. `make preflight` must pass on the current tree (Docker may be skipped). Do not bump the version — `0.1.0` is correct right now.

Acceptance: `make preflight` green; `python scripts/check-versions.py` exits 0; `make release` dry-run behaviour explained; workflow diff is one step.

---

## Wave 2 — Verification (~10 min)

Spawn **E** after B, C and D report done.

> Read-only verification of /Users/francesco/dev/tecnocasa-mcp. Do not modify files.
> 1. `git status` — confirm only expected paths changed; list anything outside `assets/`, `docs/submissions/`, `scripts/`, `Makefile`, `.github/workflows/ci.yml`, and the two README demo insertions.
> 2. Run `make preflight` and `python3 scripts/check-versions.py`.
> 3. Validate every JSON/YAML file touched: `server.json`, `glama.json`, issue templates, workflow. Run `bash -n scripts/preflight.sh` and `python -m py_compile scripts/*.py`.
> 4. Confirm `assets/demo.gif` < 5 MB and `social-preview.png` is 1280×640 (`file` / `sips -g pixelWidth -g pixelHeight`).
> 5. Confirm the README demo `<img>` URL matches the committed filename and alt text is present in both languages.
> 6. Re-check tool count = 7 across `server.py`, `docs/tools.md`, both READMEs.
> 7. Scan all tracked files for `/Users/` and for `server.py` references outside `src/tecnocasa_mcp/`.
> 8. Report a pass/fail table plus a single recommended follow-up list.

Gate: all pass → merge. Any fail → send the failing item back to the owning agent with its report, not to a new agent.

---

## Wave 3 — Merge and retag (main thread)

1. Review each workstream diff with `git diff`, commit one commit per workstream (B, C, D).
2. Update `CHANGELOG.md` release date to 2026-10-20 if it changed.
3. **Move the local tag** — safe because nothing was pushed:
   ```sh
   git tag -d v0.1.0
   git tag -a v0.1.0 -m "tecnocasa-mcp 0.1.0"
   ```
4. Confirm `git status` clean and `git log --oneline` reads as a coherent release.
5. Stop. Pushing is the human handoff.

Do not let an agent run `git tag`, `git push`, or `gh release`.

---

## Human handoff (≈20 minutes)

After Wave 3:

1. **PyPI** → pending publisher (`tecnocasa-mcp` / `francesco-plt` / `tecnocasa-mcp` / `ci.yml` / `pypi`), GitHub environment `pypi`. *(5 min)*
2. `git push origin main && git push origin v0.1.0`. *(1 min)*
3. GitHub About panel + social preview + Discussions + branch protection, using `docs/submissions/01-github-settings.md`. *(5 min)*
4. `mcp-publisher login github && mcp-publisher publish`, using `02-official-registry.md`. *(3 min)*
5. Directory forms using `03-directories.md`, `04-awesome-pr.md`. *(6 min)*
6. Show HN / Reddit / X using `05-launch.md`. *(10 min, separate sitting)*

Optionally, once `gh auth login` works, run the prepared `gh repo edit` command from the pack to set description, homepage and topics in one shot.

---

## Failure modes

| Failure | Response |
|---|---|
| No SVG rasterizer for the social preview | Chrome headless screenshot at 1280×640; commit the HTML used |
| Screencast tool unavailable | Ship static `assets/demo.png`; leave the GIF as a follow-up issue; do not ship a broken `<img>` |
| GIF > 5 MB | lower fps to 10, width to 800, or trim to 15 s |
| Agents touch shared files | revert that hunk, apply the change from the agent's reported patch |
| `make preflight` needs network (uv sync / twine) | retry once; if offline, report which step was skipped rather than weakening the script |
| Docker unavailable | `SKIP_DOCKER=1 make preflight`; record it in the report |

## Time budget

| Wave | Wall clock |
|---|---|
| 0 audit | 10 min |
| 1 builders (parallel) | 30–45 min |
| 2 verification | 10 min |
| 3 merge + retag | 10 min |
| Human handoff | ~20 min + launch sitting |

Agent selection note: `cavecrew-*` subagents are not configured in this environment, so the plan uses `explore` for read-only work and `general` for builders. If caveman-compressed output is wanted, load the `cavecrew` skill and map A/E → investigator, B/C/D → builder, V → reviewer.
