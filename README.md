# atlassian-cli

CLI for Atlassian Server and Data Center products.

## Install

`python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`

## GitHub Actions

The repository ships two GitHub Actions workflows:

- `CI`: runs on every pull request and on pushes to `main` and `release/*`
- `Release`: runs on tags matching `v*` and can also be started manually with `workflow_dispatch`

`CI` is intended to back branch protection for `main` and `release/*`.

## Release Binaries

Tagged releases publish standalone CLI bundles for:

- `linux/amd64`
- `darwin/arm64`

Each release uploads:

- `atlassian-cli_<version>_linux_amd64.tar.gz`
- `atlassian-cli_<version>_darwin_arm64.tar.gz`
- `checksums.txt`

## Install From GitHub Release

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

- `atlassian jira issue get OPS-1`
- `atlassian confluence page get 1234`
- `atlassian bitbucket repo get OPS infra`
- `atlassian bitbucket pr list SDK rte_sdk`
- `atlassian bitbucket pr list SDK rte_sdk --output json`

## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.agoralab.co --header 'accessToken: ...' bitbucket pr list SDK rte_sdk`

Config file example:

```toml
[headers]
X-Request-Source = "agora-oauth"

[bitbucket]
deployment = "dc"
url = "https://bitbucket.agoralab.co"
auth = "pat"

[bitbucket.headers]
accessToken = "$(agora-oauth token)"
```

- `atlassian bitbucket pr list SDK rte_sdk`

Config-backed header values may execute local shell commands through `$(...)`. Treat `~/.config/atlassian-cli/config.toml` as trusted local configuration.
The default `~/.config/atlassian-cli/config.toml` file is auto-created as a template on first use.
Only top-level `[jira]`, `[confluence]`, `[bitbucket]`, and `[headers]` are supported.

## Output Modes

The CLI now uses `markdown` as the default human-readable output mode.

- Single-resource commands default to markdown detail output.
- Collection commands default to an interactive browser in a TTY.
- Collection commands fall back to markdown summary output outside a TTY.
- Use `--output json` or `--output yaml` for normalized machine-readable output.
- Use `--output raw-json` to inspect the original provider response as JSON.
- Use `--output raw-yaml` to inspect the original provider response as YAML.

Examples:

- `atlassian jira issue get OPS-1`
- `atlassian jira issue search --jql 'project = OPS'`
- `atlassian confluence space list`
- `atlassian bitbucket pr list OPS infra`
- `atlassian jira issue get OPS-1 --output json`
- `atlassian bitbucket pr list OPS infra --output json`

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

## Smoke testing

Set `ATLASSIAN_SMOKE=1` and product-specific env vars before running `.venv/bin/python -m pytest tests/integration/test_smoke.py -v`.
