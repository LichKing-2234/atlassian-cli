# atlassian-cli

CLI for Atlassian Server and Data Center products.

## Install

`python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`

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

## Smoke testing

Set `ATLASSIAN_SMOKE=1` and product-specific env vars before running `.venv/bin/python -m pytest tests/integration/test_smoke.py -v`.
