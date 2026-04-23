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

- `atlassian jira issue get OPS-1 --output json`
- `atlassian confluence page get 1234 --output json`
- `atlassian bitbucket repo get OPS infra --output json`

## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.agoralab.co --header 'accessToken: ...' bitbucket pr list SDK rte_sdk --output json`

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

- `atlassian bitbucket pr list SDK rte_sdk --output json`

Config-backed header values may execute local shell commands through `$(...)`. Treat `~/.config/atlassian-cli/config.toml` as trusted local configuration.
The default `~/.config/atlassian-cli/config.toml` file is auto-created as a template on first use.
Only top-level `[jira]`, `[confluence]`, `[bitbucket]`, and `[headers]` are supported.

## Output Modes

`json` and `yaml` now return simplified resource-shaped payloads by default.

- Use `--output raw-json` to inspect the original provider response as JSON.
- Use `--output raw-yaml` to inspect the original provider response as YAML.

## Smoke testing

Set `ATLASSIAN_SMOKE=1` and product-specific env vars before running `.venv/bin/python -m pytest tests/integration/test_smoke.py -v`.
