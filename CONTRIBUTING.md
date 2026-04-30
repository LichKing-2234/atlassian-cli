# Contributing

## Local Setup

Create a virtualenv and install development dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## Quality Checks

Run these checks before opening or updating a PR:

```bash
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

If you change CLI behavior, command output, or command wiring, also update the matching tests and user-facing docs in the same change.

If you add, remove, or rename CLI subcommands, update the live coverage map in `tests/e2e/coverage_manifest.py`.

## Smoke Testing

Set `ATLASSIAN_SMOKE=1` and the required product-specific environment variables before running:

```bash
.venv/bin/python -m pytest tests/integration/test_smoke.py -v
```

## Local e2e Testing

The repository includes a local-only live e2e suite that covers every CLI subcommand with at least one real command chain.

Live test modules:

- `tests/e2e/test_jira_live.py`
- `tests/e2e/test_confluence_live.py`
- `tests/e2e/test_bitbucket_live.py`
- `tests/e2e/test_coverage_manifest.py`

The suite shells out through `python -m atlassian_cli.main`, reuses your normal CLI config, and performs real writes against the configured Atlassian instances.

Environment:

- `.env` in the repository root is loaded automatically by `tests/e2e/support/env.py`
- process environment variables still take precedence over `.env`
- `ATLASSIAN_E2E=1`
- `ATLASSIAN_CONFIG_FILE=/path/to/config.toml` (optional)
- `ATLASSIAN_E2E_JIRA_PROJECT=DEMO`
- `ATLASSIAN_E2E_JIRA_ISSUE_TYPE=Task` (optional override when the default issue type is not writable)
- `ATLASSIAN_E2E_CONFLUENCE_SPACE='~example-user'`
- `ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE=123456` (optional override when writes must happen under a known parent page)
- `ATLASSIAN_E2E_BITBUCKET_PROJECT=DEMO`
- `ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT=DEMO`
- `ATLASSIAN_E2E_BITBUCKET_REPO=example-repo`
- `ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO=example-repo` (optional override when the configured instance does not expose the default seed repo)

Recommended run:

```bash
cp .env.example .env
$EDITOR .env
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/e2e/test_coverage_manifest.py \
  tests/e2e/test_jira_live.py \
  tests/e2e/test_confluence_live.py \
  tests/e2e/test_bitbucket_live.py \
  -m e2e -v
```

The live suite performs real writes and best-effort cleanup for Jira issues, Confluence pages/comments/attachments, Bitbucket repositories, branches, and pull requests. If cleanup fails, the tests should print residue identifiers for manual removal.

When the target instance requires business-specific Jira fields that cannot be inferred from `issue_createmeta`, provide those values through test setup or project configuration rather than hardcoding them in the suite.

## CI And Releases

The repository ships two GitHub Actions workflows:

- `CI`: runs on every pull request and on pushes to `main` and `release/*`
- `Release`: runs on tags matching `v*` and can also be started manually with `workflow_dispatch`

`CI` is intended to back branch protection for `main` and `release/*`.
