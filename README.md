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

Environment variable example:

- `export ATLASSIAN_HEADER='accessToken: ...'`
- `atlassian --url https://bitbucket.agoralab.co bitbucket pr list SDK rte_sdk --output json`

## Smoke testing

Set `ATLASSIAN_SMOKE=1` and product-specific env vars before running `.venv/bin/python -m pytest tests/integration/test_smoke.py -v`.
