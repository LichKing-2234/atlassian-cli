# Live parity evidence

Live Jira and Confluence parity tests target exactly:

- Jira Server `7.11.0`, build `711000`
- Confluence Server `6.12.4`

`test_parity_preflight_live.py` uses session fixtures from `conftest.py` to verify both targets.
Every parity live test also requests its product fixture so a version mismatch fails before that
behavior runs; it is never treated as a skip.

## Evidence ledger

`parity_manifest.py` is the maintained ledger for the accepted ordinary-user boundary. Each row
records the upstream operation, fixed-version semantic inputs, gap kind, mutation status, owning
implementation issue, and evidence status.

Use these evidence states precisely:

- `unimplemented`: the accepted gap still exists
- `implemented-but-unverified`: source checks pass but exact-version live evidence does not
- `verified`: contract, documentation, exact-version live, repository, and hosted gates pass
- `excluded`: the boundary intentionally removes the operation or input
- `unsupported`: the fixed product version documents no corresponding operation

Do not mark a row `verified` until its implementation issue contains the evidence required by
the alignment decisions.

## Mutation tests

New mutation tests receive the `cleanup_registry` fixture and register cleanup immediately after
each server-side resource is created. Pytest runs the registry during teardown even if the test
assertion fails. Cleanup runs in reverse order and attempts every callback before reporting any
cleanup failures.

Every mutation must also perform an independent server read-back before asserting success. A CLI
response that merely echoes its request is not evidence.

## Running tests

Run the affected product path against the configured live targets:

```console
ATLASSIAN_E2E=1 python -m pytest -q tests/e2e/test_parity_preflight_live.py
ATLASSIAN_E2E=1 python -m pytest -q tests/e2e/test_jira_live.py
ATLASSIAN_E2E=1 python -m pytest -q tests/e2e/test_confluence_live.py
```

The ordinary test suite skips live tests unless `ATLASSIAN_E2E=1` is set.
