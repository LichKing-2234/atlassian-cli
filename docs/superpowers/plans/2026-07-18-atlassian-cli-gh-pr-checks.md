# gh-Compatible Bitbucket PR Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `atlassian bitbucket pr checks` with the observable core behavior of `gh v2.96.0 pr checks` on Bitbucket Server 6.7.2.

**Architecture:** Resolve the pull request through the existing gh-compatible repository and PR finder, read only its current head commit, then project Bitbucket build statuses into the pinned gh checks schema. Keep projection, sorting, rendering, and outcome calculation in one focused compatibility module; keep command orchestration and polling in the existing PR command module. Reuse the current provider and build-status service without adding a second REST abstraction.

**Tech Stack:** Python 3.11+, Typer/Click, Rich display-width helpers, pytest, existing Bitbucket Server REST provider.

## Global Constraints

- `gh v2.96.0` is the behavior baseline.
- Target Atlassian Bitbucket Server version is `6.7.2`.
- Read only `fromRef.latestCommit`; never aggregate historical PR commits.
- Exit `0` for passing checks, `1` for failed checks or command errors, `8` for pending checks, `2` for cancellation, and `4` for authentication or host mismatch.
- Do not register `--required`; Bitbucket 6.7.2 does not expose per-build required state.
- Keep `--jq` and `--template` deferred to the existing shared formatter phase.
- Preserve public `commit build-status` and hidden `pr build-status` compatibility commands.
- Use only the repository-approved neutral sample data.

---

### Task 1: Check Projection And Rendering

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/pr_checks.py`
- Create: `tests/products/bitbucket/test_gh_pr_checks.py`

**Interfaces:**
- Consumes: normalized build dictionaries from `BuildStatusService.for_commit()`.
- Produces: `CHECK_FIELDS`, `CheckCounts`, `project_checks(builds)`, `render_checks(checks, tty, color, width)`, and `checks_exit_code(checks)`.

- [ ] **Step 1: Write failing projection and rendering tests**

Cover all supported fields and provider states with neutral fixtures:

```python
builds = [
    {
        "key": "DEMO-1234",
        "name": "Example pull request",
        "state": "FAILED",
        "url": "https://bitbucket.example.com/example-response",
        "description": "example response",
    }
]

assert project_checks(builds) == [{
    "bucket": "fail",
    "completedAt": "0001-01-01T00:00:00Z",
    "description": "example response",
    "event": "",
    "link": "https://bitbucket.example.com/example-response",
    "name": "Example pull request",
    "startedAt": "0001-01-01T00:00:00Z",
    "state": "FAILURE",
    "workflow": "",
}]
```

Also assert:

- `SUCCESSFUL`, `FAILED`, and `INPROGRESS` map to `pass`, `fail`, and `pending`.
- Name falls back to build key.
- Sort order is failed, pending, passing, then name and link.
- TTY output has the gh summary, tallies, symbols, and table headers.
- Non-TTY output is headerless TSV with elapsed `0`.
- `--json` field projection preserves requested field order semantically and always produces an array.
- No statuses raise `no checks reported on the '<branch>' branch` at command preflight rather than rendering an empty table.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/python -m pytest -q tests/products/bitbucket/test_gh_pr_checks.py
```

Expected: collection fails because `gh_compat.pr_checks` does not exist.

- [ ] **Step 3: Implement the minimal compatibility module**

Use one immutable projected dictionary per build and one count pass:

```python
CHECK_FIELDS = (
    "bucket", "completedAt", "description", "event", "link",
    "name", "startedAt", "state", "workflow",
)
ZERO_TIME = "0001-01-01T00:00:00Z"

def project_check(build: Mapping[str, object]) -> dict[str, object]:
    state = normalize_state(build.get("state"))
    return {
        "bucket": bucket_for_state(state),
        "completedAt": ZERO_TIME,
        "description": str(build.get("description") or ""),
        "event": "",
        "link": str(build.get("url") or ""),
        "name": str(build.get("name") or build.get("key") or ""),
        "startedAt": ZERO_TIME,
        "state": state,
        "workflow": "",
    }
```

Reuse `cell_len`, ANSI styling, and the existing table-width behavior. Do not add a general table framework.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command. Expected: all tests pass.

- [ ] **Step 5: Commit the completed projection slice**

```bash
git add src/atlassian_cli/products/bitbucket/gh_compat/pr_checks.py tests/products/bitbucket/test_gh_pr_checks.py
git commit -m "feat: add gh-compatible PR checks output"
```

### Task 2: Command Resolution, Validation, And Watch Mode

**Files:**
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Create: `tests/products/bitbucket/test_pr_checks_command.py`
- Modify: `tests/test_cli_help.py`

**Interfaces:**
- Consumes: Task 1 projection/rendering functions, `PullRequestFinder`, `PullRequestReadService`, and `BuildStatusService.for_commit()`.
- Produces: public `checks [<number> | <url> | <branch>]` command with `--fail-fast`, `--interval`, `--json`, `--repo`, `--watch`, and `--web`.

- [ ] **Step 1: Write failing parser and command tests**

Assert the exact public surface and validation order:

```text
atlassian bitbucket pr checks [<number> | <url> | <branch>]
  --fail-fast
  -i, --interval INTEGER  default 10
  --json FIELDS
  -R, --repo REPOSITORY
  -w, --web
  --watch
```

Tests must prove:

- `--fail-fast` without `--watch` exits `1` before repository/provider access.
- Explicit `--interval` without `--watch` exits `1` before repository/provider access.
- `--watch --json` exits `1` before repository/provider access.
- `--web --json` exits `1` before repository/provider access.
- `-R` without a PR selector exits `1` before local Git inference.
- `--required`, `--jq`, and `--template` are absent from help and rejected.
- Number, PR URL, branch, and omitted current-branch selection reuse the existing finder rules.
- Each sample reads `headRefOid` and `headRefName`, then only the current head's build statuses.
- Human output exits `1` on failure, `8` on pending, and `0` on pass.
- JSON output selects `CHECK_FIELDS` and exits `0` regardless of check state.
- No head commit and no checks use the exact gh errors.
- `--web` opens the resolved PR URL without fetching build statuses.
- Watch mode polls until terminal, honors fail-fast, refreshes the alternate screen in a TTY, and restores it on cancellation/error.

- [ ] **Step 2: Run command and help tests and verify RED**

Run:

```bash
PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/python -m pytest -q tests/products/bitbucket/test_pr_checks_command.py tests/test_cli_help.py
```

Expected: failures because the public command is not registered.

- [ ] **Step 3: Implement parser validation and one-shot execution**

Add `_checks_run()` beside `_view_run()` and keep static validation before authentication, repository resolution, or REST access. Resolve the PR using the same URL/repository precedence as `pr view`; fetch:

```python
pull_request = PullRequestReadService(provider).get(ref, {"headRefName", "headRefOid"})
summary = BuildStatusService(provider).for_commit(str(pull_request["headRefOid"]))
checks = project_checks(summary["results"])
```

When `--web` is set, request only `url` and open it through the existing browser helper.

- [ ] **Step 4: Implement watch mode with injected time and terminal operations**

Keep the loop local to the command module. Each poll re-reads `headRefOid` so a pushed PR head is followed. Render the current table, stop when no checks remain pending, or stop immediately on a failure with `--fail-fast`. Use `try/finally` around alternate-screen entry/exit so Ctrl-C still maps to exit `2` through `run_gh_read`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all tests pass.

- [ ] **Step 6: Run existing PR command and output tests**

Run:

```bash
PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/python -m pytest -q tests/products/bitbucket/test_pr_command.py tests/products/bitbucket/test_gh_pr_output.py
```

Expected: all tests pass without changing `pr view`, `pr list`, or compatibility behavior.

- [ ] **Step 7: Commit the public command slice**

```bash
git add src/atlassian_cli/products/bitbucket/commands/pr.py tests/products/bitbucket/test_pr_checks_command.py tests/test_cli_help.py
git commit -m "feat: add Bitbucket PR checks command"
```

### Task 3: Documentation And Live Bitbucket Coverage

**Files:**
- Modify: `README.md`
- Modify: `tests/e2e/coverage_manifest.py`
- Modify: `tests/e2e/test_bitbucket_live.py`
- Modify: `tests/test_readme.py`

**Interfaces:**
- Consumes: the public command from Task 2.
- Produces: user-facing examples, explicit limitation notes, manifest registration, and a live Server 6.7.2 assertion.

- [ ] **Step 1: Write failing documentation and manifest tests**

Require README examples for:

```bash
atlassian bitbucket pr checks 1234 -R DEMO/example-repo
atlassian bitbucket pr checks 1234 -R DEMO/example-repo --watch
atlassian bitbucket pr checks 1234 -R DEMO/example-repo --json name,state,bucket,link
```

Document that checks come from the PR head commit, `--required` is unavailable on Bitbucket 6.7.2, and jq/template remain in the shared deferred formatter phase. Add `bitbucket pr checks` to the e2e coverage manifest.

- [ ] **Step 2: Run documentation tests and verify RED**

Run:

```bash
PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/python -m pytest -q tests/test_readme.py tests/e2e/test_coverage_manifest.py
```

Expected: failure because the README and manifest do not contain `pr checks`.

- [ ] **Step 3: Update README, manifest, and live round trip**

In the existing Bitbucket PR round-trip test, publish one neutral build status to the temporary head commit through the configured provider, then assert:

```python
checked = run_json(
    live_env,
    "bitbucket", "pr", "checks", str(pr_id),
    "-R", repo_selector,
    "--json", "name,state,bucket,link",
)
assert checked == [{
    "bucket": "pass",
    "link": "https://bitbucket.example.com/example-response",
    "name": "Example pull request",
    "state": "SUCCESS",
}]
```

Use `build_live_provider()` so configured `agora-oauth` headers remain in force. Do not place credentials or live identifiers in the test.

- [ ] **Step 4: Run documentation tests and focused unit tests**

Run the Step 2 command and all Task 1/2 test paths. Expected: all pass.

- [ ] **Step 5: Run affected live e2e**

Run:

```bash
ATLASSIAN_E2E=1 PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/python -m pytest -q tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live
```

Expected: pass against Bitbucket Server 6.7.2. If the environment is unavailable, report the live verification blocker explicitly.

- [ ] **Step 6: Run repository quality gates**

```bash
PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/ruff format --check .
PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/python -m pytest -q
PYTHONPATH=src /Users/admin/atlassian-cli/.venv/bin/ruff check README.md pyproject.toml src tests docs
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 7: Scan public samples and commit**

Scan changed README, docs, tests, fixtures, and source for identifiers outside the approved neutral set, then commit:

```bash
git add README.md tests/e2e/coverage_manifest.py tests/e2e/test_bitbucket_live.py tests/test_readme.py
git commit -m "docs: document Bitbucket PR checks"
```

