# Client setup

The server speaks **stdio** and needs no environment variables. Any client that
supports stdio MCP servers can run it.

Two ways to start it:

```sh
uvx tecnocasa-mcp                                       # zero-install, needs uv
tecnocasa-mcp                                           # after pip/pipx install
docker run -i --rm tecnocasa-mcp                        # container
uv run --directory /path/to/tecnocasa-mcp python -m tecnocasa_mcp   # clone
```

`uvx` ships with [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`

Use an absolute path to the executable if your client does not inherit your
shell `PATH`.

## Claude Code

```sh
claude mcp add tecnocasa -- uvx tecnocasa-mcp
claude mcp list
```

Project-scoped instead of global:

```sh
claude mcp add --scope project tecnocasa -- uvx tecnocasa-mcp
```

## Claude Desktop

Edit
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Restart the app completely (quit from the menu bar, not just close the window).

## Cursor

Global: `~/.cursor/mcp.json`. Project: `.cursor/mcp.json`.

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

Then enable the server under Settings → MCP.

## VS Code

`.vscode/mcp.json` in the workspace, or the user-level `mcp.json`:

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

Note the key is `servers`, not `mcpServers`.

## OpenCode

`~/.config/opencode/opencode.jsonc` or a project `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
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

Or from the CLI:

```sh
opencode mcp add tecnocasa --global -- uvx tecnocasa-mcp
```

## Windsurf

`~/.codeium/windsurf/mcp_config.json`:

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

## Docker

```sh
docker build -t tecnocasa-mcp .
```

Client config:

```json
{
  "mcpServers": {
    "tecnocasa": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "tecnocasa-mcp"]
    }
  }
}
```

Use `-i` (stdin open) and no `-t`: the transport is stdio, so a TTY breaks it.

## pipx / pip

```sh
pipx install tecnocasa-mcp
# or
pip install tecnocasa-mcp
```

Then use `"command": "tecnocasa-mcp"` with no args.

## From a git clone

```sh
git clone https://github.com/francesco-plt/tecnocasa-mcp
cd tecnocasa-mcp
uv sync
uv run python -m tecnocasa_mcp
```

Client config:

```json
{
  "mcpServers": {
    "tecnocasa": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/tecnocasa-mcp",
        "python",
        "-m",
        "tecnocasa_mcp"
      ]
    }
  }
}
```

Or without cloning:

```json
{
  "mcpServers": {
    "tecnocasa": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/francesco-plt/tecnocasa-mcp",
        "tecnocasa-mcp"
      ]
    }
  }
}
```

## Verifying the install

```sh
uvx tecnocasa-mcp --version
```

The server then waits on stdin — that is expected; it is not an interactive
program. A client should show seven tools: `search_locations`,
`search_listings`, `get_listing`, `search_franchise_area`,
`get_franchise_agency`, `discover_microsites`, `aggregate_listings`.

If it does not, see [troubleshooting.md](troubleshooting.md).
