# Distribution playbook (Phase 7)

Everything in the repo is ready: packaging, CI, release workflow, README,
banner, registry manifests (`server.json`, `glama.json`) and the PyPI ownership
marker. This document is the part that needs your accounts and a browser.

Work top to bottom. Steps 0 and 1 are order-sensitive.

---

## 0. Before pushing: set up PyPI trusted publishing

The CI `publish` job authenticates to PyPI with OIDC — no token, no secret to
leak. PyPI must know which repository may publish the name.

1. Log in to <https://pypi.org> and enable 2FA.
2. Go to **Account settings → Publishing → Add a new pending publisher**.
3. Fill in exactly:

| Field | Value |
|---|---|
| PyPI Project Name | `tecnocasa-mcp` |
| Owner | `francesco-plt` |
| Repository name | `tecnocasa-mcp` |
| Workflow name | `ci.yml` |
| Environment name | `pypi` |

4. In GitHub → **Settings → Environments → New environment**, create `pypi`.
   (No secrets needed. Optionally add required reviewers.)

The workflow name must match the file (`.github/workflows/ci.yml` → `ci.yml`)
and the environment must match the `environment:` key in the publish job.

> If you skip this and push the tag, the publish job fails with
> `invalid-publisher`. You can create the publisher afterwards and re-run the
> job from the Actions tab — the release itself is fine.

## 1. Push and release

```sh
git push origin main
git push origin v0.1.0
```

If the tag does not exist yet:

```sh
git tag -a v0.1.0 -m "tecnocasa-mcp 0.1.0"
git push origin v0.1.0
```

What happens: CI runs on `main`; the tag triggers the `publish` job → builds →
uploads to PyPI → creates a GitHub Release with generated notes and the
`sdist`/`wheel` attached.

Verify:

```sh
curl -s https://pypi.org/pypi/tecnocasa-mcp/json | head -c 200
uvx tecnocasa-mcp --version
```

`uvx` may serve a cached build for a minute; `uvx --refresh tecnocasa-mcp
--version` forces it.

If the job failed: fix the cause, then **Actions → ci → Re-run failed jobs**.
Never delete and re-push a tag that partially published — bump to `v0.1.1`
instead, since PyPI files are immutable.

## 2. GitHub repository settings

Do these once; they are what people see before they read anything.

- **About panel** (top right of the repo):
  - Description: `MCP server for browsing Tecnocasa listings across Italy — national portal + franchise microsites. No API key.`
  - Website: `https://pypi.org/project/tecnocasa-mcp/`
  - Topics: `mcp`, `model-context-protocol`, `mcp-server`, `real-estate`, `italy`, `tecnocasa`, `claude`, `llm-tools`, `python`
- **Social preview**: Settings → General → Social preview → upload a
  1280×640 PNG. Reuse the banner composition from `assets/banner.svg`
  (export at 2×, add padding).
- **Features**: enable **Discussions** (the issue template links to it).
- **Topics + description** are indexed by GitHub search and by most MCP
  directories — this is free discovery, don't skip it.
- **Branch protection** on `main`: require the `test` check, require a PR for
  changes, disallow force-push.
- **Security**: enable Dependabot alerts and secret scanning.
- **Releases**: open the `v0.1.0` release, edit the body, add a "Highlights"
  section above the generated notes.

## 3. Official MCP Registry

The manifest is already committed at `server.json`. PyPI ownership is verified
through the hidden `<!-- mcp-name: … -->` line in the published README.

```sh
brew install mcp-publisher

mcp-publisher validate
mcp-publisher login github     # device flow: open the URL, enter the code
mcp-publisher publish
```

Verify:

```sh
curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.francesco-plt/tecnocasa-mcp"
```

Notes:

- `server.json` `version` must equal the **published** PyPI version. Bump both
  together on every release.
- If validation complains about the package, confirm the `mcp-name` comment is
  present in the README rendered on PyPI — it must be in the sdist metadata, so
  a release built before the comment was added will fail. In that case publish
  the comment in the next patch release.
- Name must stay `io.github.francesco-plt/…` because you authenticate with
  GitHub.

## 4. Glama

`glama.json` is committed (`{"maintainers": ["francesco-plt"]}`), which is what
Glama uses to confirm ownership.

1. Open <https://glama.ai/mcp/servers> and search for `tecnocasa-mcp`. Their
   indexer usually picks up public repos automatically within a day.
2. If it is missing: <https://glama.ai/mcp/servers/new> → connect the repo.
3. Claim it, then fill the description, categories (`Real Estate`,
   `Travel & Location`) and tags. Screenshots help.

## 5. Smithery

1. Go to <https://smithery.ai/new> and sign in with GitHub.
2. Select `francesco-plt/tecnocasa-mcp`.
3. When asked for the start command, use `uvx tecnocasa-mcp` (the committed
   `Dockerfile` is there if their builder prefers containers).
4. Publish, then test the generated install snippet.

Smithery changes its flow periodically; if the UI asks for a config file it
will generate one — commit it rather than keeping it only in their dashboard.

## 6. mcp.so

Two routes, same result:

- Form: <https://mcp.so/submit>
- GitHub: open an issue at <https://github.com/chatmcp/mcp-directory/issues/new>
  with the repo URL, one-line description and category.

## 7. PulseMCP

Submit at <https://www.pulsemcp.com/submit>. They also run a weekly newsletter
that features new servers — a good reason to submit on a Monday.

## 8. awesome-mcp-servers

PR to <https://github.com/punkpeye/awesome-mcp-servers>. Add one line to the
README, in the section matching real estate / location:

```markdown
- [francesco-plt/tecnocasa-mcp](https://github.com/francesco-plt/tecnocasa-mcp) 🐍 🏠 - Browse and filter Tecnocasa real-estate listings across Italy, including franchise microsites.
```

- `🐍` = Python, `🏠` = local server. Keep the emoji legend exact.
- One line, no trailing period issues, alphabetical placement is not required
  but appreciated.
- Read their `CONTRIBUTING.md` before opening the PR; stale instructions are
  the usual reason these PRs bounce.

## 9. One-click install links (optional, high conversion)

Once the PyPI release exists you can add install badges to the README header.
Patterns that work today:

- **VS Code**: `https://vscode.dev/redirect/mcp/install?name=tecnocasa&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22tecnocasa-mcp%22%5D%7D`
- **Cursor**: `cursor://anysphere.cursor-deeplink/mcp/install?name=tecnocasa&config=<base64-json>`

The `config` value is the URL-encoded (VS Code) or base64-encoded (Cursor) JSON
`{"command":"uvx","args":["tecnocasa-mcp"]}`. Test both on a clean profile
before adding them: if a deeplink is wrong it fails silently.

## 10. Launch

Only after the demo GIF is in the README and `uvx tecnocasa-mcp` works from a
clean machine.

**Demo asset** (the one thing not in the repo):

```sh
# 15–25 s screen capture, then:
ffmpeg -i demo.mov -vf "fps=12,scale=1000:-1" -loop 0 assets/demo.gif
```

Keep it under 5 MB. Show: a prompt, the tool call, the result cards.

**Show HN** (one shot, use it well):

- Title: `Show HN: MCP server for Tecnocasa listings across Italy`
- Body: what it does, why franchises are the interesting part, the fallback to
  microsites when the national portal blackholes. Mention no API key and
  read-only. Link the repo, not PyPI.

**Reddit**: r/mcp, r/ClaudeAI, r/ItaliaDeveloper. Same body, adapted; do not
copy-paste HN phrasing verbatim.

**Italian communities**: r/Italia, r/immobiliare (read each sub's self-promo
rules first), Developer Italia Discord/Slack groups.

**X/LinkedIn**: one post with the GIF, the one-line install, and a "why" thread
on franchise microsites.

Timing: publish on a weekday morning CET. Respond to every comment for the
first 6 hours.

## 11. Post-launch (the part that keeps stars coming)

- Reply to issues within 24–48 h. A fast first response is the single biggest
  driver of repeat contributors.
- Label 3–5 starter issues `good first issue` (see the list in `CONTRIBUTING.md`
  ideas): extra filters, more city fixtures, docs translations, Docker examples.
- Cut a patch release whenever a parser fix lands. Release cadence is visible
  on the repo page and signals health.
- Every release: bump `__version__` **and** `server.json` `pkg.version`, update
  `CHANGELOG.md`, tag, push the tag.
- Quarterly: re-check every registry listing (they rot), re-run
  `mcp-publisher publish` if the version there is stale, and refresh the demo
  GIF if the UI changed.

---

## Checklist

- [ ] PyPI pending publisher configured (`tecnocasa-mcp` / `francesco-plt` / `tecnocasa-mcp` / `ci.yml` / `pypi`)
- [ ] GitHub `pypi` environment created
- [ ] `main` and `v0.1.0` pushed; CI green; release published
- [ ] `uvx tecnocasa-mcp --version` works on a clean machine
- [ ] Repo description, website, topics set
- [ ] Social preview uploaded
- [ ] Discussions enabled, `main` protected
- [ ] `mcp-publisher publish` succeeded and the registry search returns the server
- [ ] Glama claimed
- [ ] Smithery published
- [ ] mcp.so submitted
- [ ] PulseMCP submitted
- [ ] awesome-mcp-servers PR opened
- [ ] Demo GIF added to `README.md` and `README.it.md`
- [ ] Launch posts published
- [ ] 3+ `good first issue` issues opened
