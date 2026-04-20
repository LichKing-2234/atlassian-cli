# atlassian-cli

CLI for Atlassian Server and Data Center products.

## Install

`python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`

## Examples

- `atlassian jira issue get OPS-1 --profile prod-jira --output json`
- `atlassian confluence page get 1234 --profile wiki`
- `atlassian bitbucket repo get OPS infra --profile code`

## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.agoralab.co --header 'accessToken: ...' bitbucket pr list SDK rte_sdk --output json`

Config file example:

```toml
[headers]
accessToken = "$(agora-oauth token)"

[profiles.code]
product = "bitbucket"
deployment = "dc"
url = "https://bitbucket.agoralab.co"
auth = "pat"

[profiles.code.headers]
X-Request-Source = "agora-oauth"
```

- `atlassian --profile code bitbucket pr list SDK rte_sdk --output json`

Config-backed header values may execute local shell commands through `$(...)`. Treat `~/.config/atlassian-cli/config.toml` as trusted local configuration.

## Smoke testing

Set `ATLASSIAN_SMOKE=1` and product-specific env vars before running `.venv/bin/python -m pytest tests/integration/test_smoke.py -v`.
