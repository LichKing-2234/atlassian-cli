# Bitbucket PR List Native Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore `bitbucket pr list PROJECT_KEY REPO_SLUG` alongside `-R` and make every PR-list state boundary use Bitbucket-native states with case-insensitive input.

**Architecture:** Extend the existing primary `pr list` command instead of adding a second parser or command. Centralize native state normalization in `services/pr_read.py`, use that contract from the command and search parser, and preserve the current 100-item automatic pagination loop.

**Tech Stack:** Python 3.12+, Typer/Click, pytest, Ruff, `atlassian-python-api`, live Bitbucket Server e2e.

## Global Constraints

- `pr list PROJECT_KEY REPO_SLUG`, `pr list -R PROJECT_KEY/REPO_SLUG`, and repository inference must all remain supported.
- `PROJECT_KEY` and `REPO_SLUG` must appear together and must not be combined with `-R`.
- `--state` defaults to `OPEN` and accepts only `OPEN`, `DECLINED`, `MERGED`, and `ALL`, case-insensitively.
- `closed` is not a valid state input; Bitbucket's native state is `DECLINED`.
- Human and JSON `state` output must retain `OPEN`, `DECLINED`, or `MERGED`.
- Automatic paging remains in 100-item server pages and stops at `--limit` after filtering.
- Use only the repository's approved public placeholders, including `DEMO`, `example-repo`, and `Example pull request`.
- Any changed live-covered CLI behavior must pass the affected `ATLASSIAN_E2E=1` test before completion.

---

## File Structure

- Modify `src/atlassian_cli/products/bitbucket/commands/pr.py`: paired positional parsing, `-R` conflict validation, native state preflight, and repository selection.
- Modify `src/atlassian_cli/products/bitbucket/services/pr_read.py`: shared state normalization, native search semantics, native projection, and unchanged automatic pagination.
- Modify `src/atlassian_cli/products/bitbucket/gh_compat/pr_output.py`: render `DECLINED` with the closed-state color without renaming it.
- Modify `tests/products/bitbucket/test_pr_command.py`: command grammar, state input, web URL, compatibility output, and pre-I/O errors.
- Modify `tests/products/bitbucket/test_pr_read_service.py`: service state normalization, search rules, provider calls, and native projected output.
- Modify `tests/products/bitbucket/test_gh_pr_output.py`: human rendering of native `DECLINED` state.
- Modify `tests/test_cli_help.py`: optional positional metavars and native state help.
- Modify `tests/test_readme.py`: lock the documented dual grammar and native state contract.
- Modify `tests/e2e/test_bitbucket_live.py`: live coverage for `-R` plus paired positional invocation.
- Modify `README.md`: current syntax, native state values, compatibility examples, and migration text.
- Modify `docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-design.md`: record the approved native-state and positional deviations.
- Modify `docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-matrix.md`: classify both deviations without changing the pinned gh oracle.

---

### Task 1: Restore Paired Positionals and Native Command-State Input

**Files:**
- Modify: `tests/products/bitbucket/test_pr_command.py`
- Modify: `tests/test_cli_help.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`

**Interfaces:**
- Consumes: existing `resolve_repository(server, explicit=...)` and `run_gh_read(...)`.
- Produces: `_list_repository_selector(project_key: str | None, repo_slug: str | None, repo: str | None) -> str | None`; primary `list_pull_requests` with optional paired positionals; command-level use of `normalize_pull_request_state(value: str) -> str`. Add the normalization function to `services/pr_read.py` during this task as the minimal shared interface required by the command tests; Task 2 applies it to the rest of the service.

- [ ] **Step 1: Write failing command tests for paired positionals**

Add focused tests that pass `DEMO example-repo` through the real Typer parser and assert the resolved repository reaches the list service:

```python
def test_primary_list_accepts_legacy_project_repo_positionals(monkeypatch) -> None:
    calls = install_read_fakes(monkeypatch)

    result = runner.invoke(
        app,
        primary_list_args("DEMO", "example-repo", "--json", "number", include_repo=False),
    )

    assert result.exit_code == 0
    assert calls["lists"][0][0].slug == "DEMO/example-repo"
```

Adjust `primary_list_args` to accept `include_repo: bool = True` so existing tests retain `-R` and the new test can omit it.

Add two pre-I/O validation tests:

```python
@pytest.mark.parametrize("positionals", [["DEMO"], ["DEMO", "example-repo", "extra"]])
def test_primary_list_rejects_incomplete_or_extra_positionals(positionals, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    result = runner.invoke(app, ["bitbucket", "pr", "list", *positionals])
    assert result.exit_code == 1


def test_primary_list_rejects_positionals_with_repo_option(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    result = runner.invoke(
        app,
        ["bitbucket", "pr", "list", "DEMO", "example-repo", "-R", "DEMO/example-repo"],
    )
    assert result.exit_code == 1
    assert "cannot use `PROJECT_KEY REPO_SLUG` with `--repo`" in result.stderr
```

- [ ] **Step 2: Write failing command tests for native states**

Replace gh-state parameterizations with the native contract:

```python
@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        ("OPEN", "OPEN"),
        ("open", "OPEN"),
        ("DECLINED", "DECLINED"),
        ("declined", "DECLINED"),
        ("MERGED", "MERGED"),
        ("merged", "MERGED"),
        ("ALL", "ALL"),
        ("all", "ALL"),
    ],
)
def test_primary_list_accepts_native_states_case_insensitively(
    value: str, normalized: str, monkeypatch
) -> None:
    calls = install_read_fakes(monkeypatch)
    result = runner.invoke(app, primary_list_args("--state", value, "--json", "number"))
    assert result.exit_code == 0
    assert calls["lists"][0][1].state == normalized


@pytest.mark.parametrize("value", ["closed", "draft", "superseded"])
def test_primary_list_rejects_non_native_states_before_context(value, monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    result = runner.invoke(app, ["bitbucket", "pr", "list", "--state", value])
    assert result.exit_code == 1
    assert f"invalid state: {value}" in result.stderr
```

Update the hidden `--output` assertions so lowercase native values map only by uppercasing; remove the `closed -> DECLINED` case and assert `declined -> DECLINED`.

- [ ] **Step 3: Update the help test to require optional positionals and native state help**

Extend `test_pr_list_help_matches_first_slice`:

```python
assert "[PROJECT_KEY]" in output
assert "[REPO_SLUG]" in output
for state in ("OPEN", "DECLINED", "MERGED", "ALL"):
    assert state in output
assert "closed" not in output
```

- [ ] **Step 4: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/products/bitbucket/test_pr_command.py \
  tests/test_cli_help.py
```

Expected: failures show that `pr list` rejects the positional pair, defaults to `open`, accepts `closed`, and omits native state help.

- [ ] **Step 5: Implement paired repository selection and command state normalization**

In `services/pr_read.py`, introduce the shared state boundary:

```python
BITBUCKET_PULL_REQUEST_STATES = frozenset({"OPEN", "DECLINED", "MERGED", "ALL"})


def normalize_pull_request_state(value: str) -> str:
    normalized = value.upper()
    if normalized not in BITBUCKET_PULL_REQUEST_STATES:
        raise ValueError(f"invalid state: {value}")
    return normalized
```

Import it in `commands/pr.py`. Replace the command `_STATE_MAP` and validation with this function, translating `ValueError` into `GhPreflightError` with the same message.

Add the paired-selector helper:

```python
def _list_repository_selector(
    project_key: str | None,
    repo_slug: str | None,
    repo: str | None,
) -> str | None:
    if (project_key is None) != (repo_slug is None):
        raise GhPreflightError("PROJECT_KEY and REPO_SLUG must be provided together")
    if project_key is not None and repo is not None:
        raise GhPreflightError("cannot use `PROJECT_KEY REPO_SLUG` with `--repo`")
    if project_key is not None:
        return f"{project_key}/{repo_slug}"
    return repo
```

Add optional Typer arguments to `list_pull_requests`:

```python
project_key: str | None = typer.Argument(None, metavar="[PROJECT_KEY]"),
repo_slug: str | None = typer.Argument(None, metavar="[REPO_SLUG]"),
```

Pass them into `_list_run`, resolve the selector before context/authentication, and define the state option as:

```python
state: str = typer.Option(
    "OPEN",
    "--state",
    "-s",
    help="Bitbucket pull request state: OPEN, DECLINED, MERGED, or ALL.",
),
```

Use the normalized state directly for browser URLs, legacy output, filtering, and `PullRequestListFilters`.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the Step 4 command.

Expected: command and help suites pass with no warnings beyond tests explicitly exercising the deprecated hidden output.

- [ ] **Step 7: Commit Task 1**

```bash
git add \
  src/atlassian_cli/products/bitbucket/commands/pr.py \
  src/atlassian_cli/products/bitbucket/services/pr_read.py \
  tests/products/bitbucket/test_pr_command.py \
  tests/test_cli_help.py
git commit -m "fix: preserve native Bitbucket PR list inputs"
```

---

### Task 2: Preserve Native State Through Search, Service, and Output

**Files:**
- Modify: `tests/products/bitbucket/test_pr_read_service.py`
- Modify: `tests/products/bitbucket/test_gh_pr_output.py`
- Modify: `src/atlassian_cli/products/bitbucket/services/pr_read.py`
- Modify: `src/atlassian_cli/products/bitbucket/gh_compat/pr_output.py`

**Interfaces:**
- Consumes: `normalize_pull_request_state(value: str) -> str` and `BITBUCKET_PULL_REQUEST_STATES` from Task 1.
- Produces: `PullRequestListFilters.state` normalized at service entry; `parse_search_query` qualifiers containing uppercase native states; `_direct_projection` retaining the raw native state.

- [ ] **Step 1: Write failing service tests for native state and search semantics**

Replace `test_list_maps_state_to_server_state` with native, case-insensitive inputs:

```python
@pytest.mark.parametrize(
    ("state", "server_state"),
    [("OPEN", "OPEN"), ("open", "OPEN"), ("DECLINED", "DECLINED"),
     ("declined", "DECLINED"), ("MERGED", "MERGED"), ("all", "ALL")],
)
def test_list_normalizes_native_state_case_insensitively(state, server_state) -> None:
    provider = FakeProvider([raw_pr(state="OPEN"), raw_pr(pr_id=1235, state="DECLINED")])
    PullRequestReadService(provider).list(REPO, PullRequestListFilters(state=state), {"number"})
    assert provider.list_calls[0] == (server_state, 0, 100)
```

Add search tests:

```python
@pytest.mark.parametrize("query", ["state:closed", "is:closed", "state:draft"])
def test_search_rejects_non_native_states(query: str) -> None:
    with pytest.raises(ValueError, match="unsupported .* search value"):
        parse_search_query(query)


@pytest.mark.parametrize("query", ["state:DECLINED", "state:declined", "is:MERGED"])
def test_search_accepts_native_states_case_insensitively(query: str) -> None:
    parsed = parse_search_query(query)
    assert parsed["qualifiers"][0][1] in {"DECLINED", "MERGED"}
```

Update the explicit-state predicate test to use `state="DECLINED"` and `search="state:OPEN"`.

- [ ] **Step 2: Write failing projection and presenter tests for `DECLINED`**

Change `test_direct_projection_uses_slug_user_fallback_and_closed_date` to expect:

```python
"state": "DECLINED"
```

In `test_gh_pr_output.py`, add a human-list fixture whose state is `DECLINED` and assert the rendered line contains `DECLINED`, not `CLOSED`.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/products/bitbucket/test_pr_read_service.py \
  tests/products/bitbucket/test_gh_pr_output.py
```

Expected: failures show `closed` is still accepted, search qualifiers are stored as gh values, and `DECLINED` is projected as `CLOSED`.

- [ ] **Step 4: Implement native service and output behavior**

In `services/pr_read.py`:

- set `PullRequestListFilters.state` default to `OPEN`;
- normalize `filters.state` at the beginning of `list`;
- use `state == "OPEN"` when deciding whether a search state replaces the default;
- normalize state search values with `normalize_pull_request_state` and preserve the existing qualifier-specific error wording;
- store uppercase states in search qualifiers and compare them directly with raw Bitbucket states;
- return `raw["state"]` from `_direct_projection`.

In `gh_compat/pr_output.py`, change the color lookup to:

```python
return {"OPEN": "32", "DECLINED": "31", "MERGED": "35"}.get(str(state), "")
```

Do not change the separate boolean JSON field named `closed`; only the state enum changes.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 3 command.

Expected: both suites pass.

- [ ] **Step 6: Run all Bitbucket unit tests**

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/products/bitbucket
```

Expected: all Bitbucket tests pass; update only assertions that intentionally encoded the replaced gh-state contract.

- [ ] **Step 7: Commit Task 2**

```bash
git add \
  src/atlassian_cli/products/bitbucket/services/pr_read.py \
  src/atlassian_cli/products/bitbucket/gh_compat/pr_output.py \
  tests/products/bitbucket/test_pr_read_service.py \
  tests/products/bitbucket/test_gh_pr_output.py
git commit -m "fix: retain native Bitbucket pull request states"
```

---

### Task 3: Document and Live-Verify the Compatibility Contract

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-design.md`
- Modify: `docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-matrix.md`
- Modify: `tests/test_readme.py`
- Modify: `tests/e2e/test_bitbucket_live.py`

**Interfaces:**
- Consumes: the final `pr list` grammar and native-state contract from Tasks 1-2.
- Produces: user-facing migration guidance and live evidence for both repository selectors.

- [ ] **Step 1: Write the failing README contract test**

Update `test_readme_documents_gh_compatible_bitbucket_pr_reads` so it requires both repository forms and native states:

```python
assert "atlassian bitbucket pr list DEMO example-repo" in readme
assert "atlassian bitbucket pr list -R DEMO/example-repo" in readme
for state in ("OPEN", "DECLINED", "MERGED", "ALL"):
    assert state in readme
assert "Its `closed` state maps" not in readme
```

Remove the old assertion that `atlassian bitbucket pr list DEMO example-repo` is absent.

- [ ] **Step 2: Run the README test and verify RED**

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_readme.py
```

Expected: FAIL because README still documents only `-R` and the gh `closed` mapping.

- [ ] **Step 3: Extend the live e2e with the paired positional form**

After the existing `-R` list assertion, add:

```python
listed_via_positionals = run_json(
    live_env,
    "bitbucket",
    "pr",
    "list",
    target["project_key"],
    target["repo_slug"],
    "--state",
    "open",
    "--json",
    "number,state",
)
assert any(item == {"number": pr_id, "state": "OPEN"} for item in listed_via_positionals)
```

This covers paired positionals, lowercase accepted input, native uppercase output, and the unchanged automatic list service in one live call.

- [ ] **Step 4: Update README examples and migration text**

Lead with the repository-standard positional form and show `-R` as an alternative:

```markdown
- `atlassian bitbucket pr list DEMO example-repo`
- `atlassian bitbucket pr list -R DEMO/example-repo --state DECLINED --limit 30`
```

Document accepted states as `OPEN`, `DECLINED`, `MERGED`, and `ALL`, case-insensitively. Replace the migration row that claims `pr list PROJECT REPO` was removed with a row stating both forms are supported. Retain the existing `pr browse` explanation.

- [ ] **Step 5: Update the pinned parity documentation without rewriting the oracle**

In the parity matrix:

- keep the gh baseline row as evidence;
- classify `PROJECT_KEY REPO_SLUG` plus `-R` as a local compatibility deviation;
- classify native case-insensitive states and native `DECLINED` output as a new deviation;
- update the migration matrix so `pr list` is no longer described as breaking.

In the parity design, replace the `pr list` breaking-migration language with the approved dual grammar and state deviation. Do not change unrelated future command plans.

- [ ] **Step 6: Run the README test and documentation checks**

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_readme.py
git diff --unified=0 origin/main...HEAD -- README.md docs tests/e2e/test_bitbucket_live.py
git diff --check
```

Expected: the README test passes; every sample identifier in the zero-context diff belongs to the approved placeholder set; `git diff --check` exits `0`.

- [ ] **Step 7: Run the affected live Bitbucket e2e**

```bash
ATLASSIAN_E2E=1 PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live
```

Expected: `1 passed`. If the configured live environment is unavailable, stop and report the exact blocker instead of claiming live verification.

- [ ] **Step 8: Run the repository quality gates**

```bash
.venv/bin/ruff format --check .
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: format and lint exit `0`; the full suite passes with only the repository's expected e2e skips when `ATLASSIAN_E2E` is not set.

- [ ] **Step 9: Commit Task 3**

```bash
git add \
  README.md \
  docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-design.md \
  docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-matrix.md \
  tests/e2e/test_bitbucket_live.py \
  tests/test_readme.py
git commit -m "docs: document native Bitbucket PR list compatibility"
```

---

## Final Review

- [ ] Confirm `git diff origin/main...HEAD --check` exits `0`.
- [ ] Confirm `git log --oneline origin/main..HEAD` contains the design, input compatibility, native state, and documentation commits.
- [ ] Confirm no unrelated files changed and the original main worktree remains untouched.
- [ ] Review every requirement in `docs/superpowers/specs/2026-07-18-atlassian-cli-pr-list-native-compat-design.md` against the final diff.
