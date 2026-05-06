# atlassian-cli

CLI for Atlassian Server and Data Center products.

## Install

`python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`

## Install From GitHub Release

Tagged releases publish standalone bundles for `linux/amd64` and `darwin/arm64`, plus `checksums.txt`.

Install the latest binary release:

```bash
curl -fsSL https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/main/install.sh | sh
```

Install a specific release:

```bash
curl -fsSL https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/main/install.sh | env INSTALL_VERSION=v0.1.0 sh
```

By default the installer writes an `atlassian` launcher to `~/.local/bin` and installs the runtime bundle under `~/.local/bin/.atlassian-cli`.

You can also download a tarball from the GitHub Release page and run `atlassian/atlassian` from the extracted bundle.

`darwin/arm64` binaries are unsigned in the first release version, so macOS may require a manual Gatekeeper allow step on first run.

## Examples

- `atlassian jira issue get DEMO-1`
- `atlassian confluence page get 1234`
- `atlassian bitbucket repo get DEMO example-repo`
- `atlassian bitbucket pr list DEMO example-repo`
- `atlassian bitbucket pr list DEMO example-repo --output json`

## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.example.com --header 'accessToken: ...' bitbucket pr list DEMO example-repo`

Config file example:

```toml
[headers]
X-Request-Source = "example-oauth"

[bitbucket]
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"

[bitbucket.headers]
accessToken = "$(example-oauth token)"
```

- `atlassian bitbucket pr list DEMO example-repo`

Config-backed header values may execute local shell commands through `$(...)`. Treat `~/.config/atlassian-cli/config.toml` as trusted local configuration.
The default `~/.config/atlassian-cli/config.toml` file is auto-created as a template on first use.
Only top-level `[jira]`, `[confluence]`, `[bitbucket]`, and `[headers]` are supported.

## Output Modes

The CLI now uses `markdown` as the default human-readable output mode.

- Single-resource commands default to markdown detail output.
- Collection commands default to an interactive browser in a TTY.
- Collection commands fall back to markdown summary output outside a TTY.
- Confluence page detail output renders storage HTML content into readable Markdown in `--output markdown`.
- Use `--output json` or `--output yaml` for normalized machine-readable output.
- Use `--output raw-json` to inspect the original provider response as JSON.
- Use `--output raw-yaml` to inspect the original provider response as YAML.

Examples:

- `atlassian jira issue get DEMO-1`
- `atlassian jira issue search --jql 'project = DEMO'`
- `atlassian confluence space list`
- `atlassian bitbucket pr list DEMO example-repo`
- `atlassian jira issue get DEMO-1 --output json`
- `atlassian bitbucket pr list DEMO example-repo --output json`

### Interactive browser behavior

TTY collection commands open a compact browser instead of printing a long static list.

- The top region is a dense single-line-per-item list for fast scanning.
- The bottom preview is a live preview that shows metadata for the selected item without opening full detail.
- `Enter` opens the full markdown detail view for the selected item.
- `b` or `Esc` returns from detail to the list.
- `/` filters only the items already loaded into the current browser session.
- `r` refreshes the first page and returns the browser to list mode.

Keybindings:

`j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit`

## Scope

The CLI now covers the `mcp-atlassian` `TOOLSETS=default` Jira and Confluence command groups for Server/Data Center:

- Jira issues, fields, comments, and transitions
- Confluence pages and comments

Normalized json and yaml output now follows MCP-style resource envelopes more closely. This is a breaking change for scripts that consumed older normalized output.

Raw modes with unchanged behavior:

- `raw-json`
- `raw-yaml`

One default MCP capability remains explicitly unsupported in CLI v1: Jira batch changelog fetch. That workflow depends on Cloud support, and the current CLI still rejects `--deployment cloud`.

## Contributing

Contributor workflows, including local setup, smoke tests, live e2e execution, CI/release notes, and maintenance checklists, are documented in [CONTRIBUTING.md](CONTRIBUTING.md).
