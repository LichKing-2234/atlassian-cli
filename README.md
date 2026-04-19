# atlassian-cli

CLI for Atlassian Server and Data Center products.

## Install

`python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`

## Examples

- `atlassian jira issue get OPS-1 --profile prod-jira --output json`
- `atlassian confluence page get 1234 --profile wiki`
- `atlassian bitbucket repo get OPS infra --profile code`

## Smoke testing

Set `ATLASSIAN_SMOKE=1` and product-specific env vars before running `.venv/bin/python -m pytest tests/integration/test_smoke.py -v`.
