# gh-Compatible Bitbucket PR Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `atlassian bitbucket pr edit` with the Bitbucket-applicable grammar and observable behavior of `gh v2.96.0 pr edit`.

**Architecture:** Reuse the existing gh-compatible repository resolver and PR finder, then hand an immutable edit request to a focused fetch-modify-PUT service. Keep TTY prompting and file/stdin parsing in a small compatibility module, keep Bitbucket payload construction in the service, and expose one provider update primitive.

**Tech Stack:** Python 3.11+, Typer/Click, atlassian-python-api, pytest, Ruff, existing Bitbucket Server/Data Center live e2e harness.

## Global Constraints

- Treat `gh v2.96.0` as the command, flag, selector, exit, and output baseline.
- Register only Bitbucket-supported fields: title, body, destination branch, and individual reviewers.
- Do not register GitHub-only assignee, label, project, milestone, team, or Copilot inputs.
- Preserve explicit empty title/body values and validate `--body` versus `--body-file` before I/O.
- Use the fetched Bitbucket PR version exactly once; do not retry stale writes.
- Use only approved public placeholders such as `DEMO`, `DEMO-1234`, `example-repo`, and `reviewer-one`.
- Run Python and Ruff from the shared `../../.venv` with `PYTHONPATH=$PWD/src` inside the worktree.

---

## File Structure

- Create `src/atlassian_cli/products/bitbucket/services/pr_edit.py`: immutable edit request, payload construction, reviewer desired-state merge, and fetch-modify-PUT service.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/pr_edit.py`: body input, repeated/comma reviewer normalization, and injectable TTY prompt adapter.
- Modify `src/atlassian_cli/products/bitbucket/providers/base.py`: declare the PR update primitive.
- Modify `src/atlassian_cli/products/bitbucket/providers/server.py`: delegate PR updates to the Atlassian client.
- Modify `src/atlassian_cli/products/bitbucket/gh_compat/pr_finder.py`: allow the `pr edit -R` current-branch exception without changing read commands.
- Modify `src/atlassian_cli/products/bitbucket/commands/pr.py`: register and orchestrate `pr edit`.
- Create `tests/products/bitbucket/test_pr_edit_service.py`: payload and concurrency behavior.
- Create `tests/products/bitbucket/test_gh_pr_edit.py`: input and prompt behavior.
- Create `tests/products/bitbucket/test_pr_edit_command.py`: grammar, selectors, exits, and output.
- Modify `tests/products/bitbucket/test_provider.py`: exact provider delegation.
- Modify `tests/products/bitbucket/test_gh_pr_finder.py`: edit-only `-R` exception.
- Modify `tests/e2e/coverage_manifest.py` and `tests/e2e/test_bitbucket_live.py`: command ownership and live PUT verification.
- Modify `tests/test_readme.py` and `README.md`: public command examples and capability limits.

---

### Task 1: Add the Provider Update Primitive

**Files:**
- Modify: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Test: `tests/products/bitbucket/test_provider.py`

**Interfaces:**
- Consumes: installed `Bitbucket.update_pull_request(project_key, repository_slug, pull_request_id, data)`.
- Produces: `BitbucketProvider.update_pull_request(project_key: str, repo_slug: str, pr_id: int, payload: dict) -> dict`.

- [ ] **Step 1: Write the failing delegation test**

Append a provider test with an exact call assertion:

```python
def test_bitbucket_provider_update_pull_request_forwards_payload() -> None:
    calls = {}
    payload = {"version": 7, "title": "Example pull request"}

    class FakeClient:
        def update_pull_request(self, project_key, repo_slug, pr_id, data):
            calls["args"] = (project_key, repo_slug, pr_id, data)
            return {**data, "id": pr_id}

    provider = build_provider_with_client(FakeClient())

    result = provider.update_pull_request("DEMO", "example-repo", 1234, payload)

    assert result["id"] == 1234
    assert calls["args"] == ("DEMO", "example-repo", 1234, payload)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/python -m pytest -q \
  tests/products/bitbucket/test_provider.py::test_bitbucket_provider_update_pull_request_forwards_payload
```

Expected: fail because `BitbucketServerProvider.update_pull_request` does not exist.

- [ ] **Step 3: Add the protocol and delegation**

Add the protocol signature and this provider method:

```python
def update_pull_request(
    self,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    payload: dict,
) -> dict:
    return self.client.update_pull_request(project_key, repo_slug, pr_id, payload)
```

- [ ] **Step 4: Verify GREEN**

Run the focused test from Step 2 and then:

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/python -m pytest -q \
  tests/products/bitbucket/test_provider.py
```

Expected: all provider tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/atlassian_cli/products/bitbucket/providers/base.py \
  src/atlassian_cli/products/bitbucket/providers/server.py \
  tests/products/bitbucket/test_provider.py
git commit -m "feat: add Bitbucket pull request update primitive"
```

---

### Task 2: Build the Fetch-Modify-PUT Edit Service

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/services/pr_edit.py`
- Create: `tests/products/bitbucket/test_pr_edit_service.py`

**Interfaces:**
- Consumes: `BitbucketProvider.get_pull_request(...)` and `update_pull_request(...)`.
- Produces: `PullRequestEdits`, `PullRequestEditService.load(ref)`, and `PullRequestEditService.edit(ref, edits, current=None)`.

- [ ] **Step 1: Write failing tests for field edits and versioned payloads**

Use a raw fixture containing complete refs, links, and reviewers:

```python
RAW_PR = {
    "id": 1234,
    "version": 7,
    "title": "Example pull request",
    "description": "example response",
    "fromRef": {
        "id": "refs/heads/feature/DEMO-1234/example-change",
        "repository": {"slug": "example-repo", "project": {"key": "DEMO"}},
    },
    "toRef": {
        "id": "refs/heads/main",
        "repository": {"slug": "example-repo", "project": {"key": "DEMO"}},
    },
    "reviewers": [{"user": {"name": "reviewer-one"}, "approved": True}],
    "links": {"self": [{"href": "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"}]},
}
```

Test that `PullRequestEdits(title="", body="", base="develop")` sends one PUT with version `7`, explicit empty strings, `refs/heads/develop`, unchanged source ref/reviewer, and no second GET when `current` is supplied. Test the default path performs exactly one GET and one PUT.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/python -m pytest -q \
  tests/products/bitbucket/test_pr_edit_service.py
```

Expected: collection fails because `services.pr_edit` does not exist.

- [ ] **Step 3: Implement the immutable request and payload builder**

Create:

```python
from copy import deepcopy
from dataclasses import dataclass

from atlassian_cli.core.errors import TransportError
from atlassian_cli.products.bitbucket.gh_compat.selectors import PullRequestRef
from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider


@dataclass(frozen=True)
class PullRequestEdits:
    title: str | None = None
    body: str | None = None
    base: str | None = None
    add_reviewers: tuple[str, ...] = ()
    remove_reviewers: tuple[str, ...] = ()

    def dirty(self) -> bool:
        return any(
            value is not None
            for value in (self.title, self.body, self.base)
        ) or bool(self.add_reviewers or self.remove_reviewers)
```

Implement helpers that require a mapping response, read reviewer identity in
`name`, `slug`, `username` order, make removals win, prefix non-qualified base
branches with `refs/heads/`, preserve retained reviewer objects with
`deepcopy()`, and build only `version`, `title`, `description`, `fromRef`,
`toRef`, and `reviewers`.

Implement:

```python
class PullRequestEditService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def load(self, ref: PullRequestRef) -> dict:
        raw = self.provider.get_pull_request(
            ref.repository.project_key,
            ref.repository.repo_slug,
            ref.number,
        )
        if not isinstance(raw, dict):
            raise TransportError("invalid Bitbucket pull request response")
        return raw

    def edit(
        self,
        ref: PullRequestRef,
        edits: PullRequestEdits,
        *,
        current: dict | None = None,
    ) -> dict:
        current = self.load(ref) if current is None else current
        payload = build_update_payload(current, edits)
        return self.provider.update_pull_request(
            ref.repository.project_key,
            ref.repository.repo_slug,
            ref.number,
            payload,
        )
```

- [ ] **Step 4: Add reviewer desired-state tests**

Cover repeated/case-sensitive Bitbucket logins, retaining raw approved reviewer
objects, adding `reviewer-two`, removing `reviewer-one`, add/remove conflict with
removal winning, and no-op add/remove requests. Assert the final order is
existing retained reviewers followed by new reviewer inputs.

- [ ] **Step 5: Verify GREEN**

Run the service test file. Expected: all tests pass with one GET and one PUT per
edit path.

- [ ] **Step 6: Commit**

```bash
git add src/atlassian_cli/products/bitbucket/services/pr_edit.py \
  tests/products/bitbucket/test_pr_edit_service.py
git commit -m "feat: add pull request edit service"
```

---

### Task 3: Add gh-Compatible Edit Input Helpers

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/pr_edit.py`
- Create: `tests/products/bitbucket/test_gh_pr_edit.py`

**Interfaces:**
- Consumes: `PullRequestEdits` and raw Bitbucket PR data.
- Produces: `normalize_reviewer_values`, `read_body_file`, and `prompt_for_edits`.

- [ ] **Step 1: Write failing normalization and file-input tests**

Test repeated and comma-separated values:

```python
assert normalize_reviewer_values(
    ["reviewer-one,reviewer-two", "reviewer-one", " reviewer-three "],
) == ("reviewer-one", "reviewer-two", "reviewer-three")
```

Test that blank segments are ignored, a normal UTF-8 file is read exactly, `-`
reads an injected `StringIO` once, and a missing file raises the original clear
filesystem error.

- [ ] **Step 2: Verify RED**

Run the new test file. Expected: collection fails because the compatibility
module does not exist.

- [ ] **Step 3: Implement deterministic input helpers**

Use insertion-ordered de-duplication and dependency injection:

```python
def normalize_reviewer_values(values: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in value.split(","):
            login = item.strip()
            if login and login not in seen:
                seen.add(login)
                normalized.append(login)
    return tuple(normalized)


def read_body_file(value: str, *, stdin: TextIO) -> str:
    return stdin.read() if value == "-" else Path(value).read_text(encoding="utf-8")
```

- [ ] **Step 4: Write failing injectable prompt tests**

Use a fake prompt callable to test field selection validation, seeded title/base
defaults, explicit empty results, reviewer desired-state conversion, and
cancel/no-selection behavior without a real terminal.

- [ ] **Step 5: Implement the prompt adapter**

Define a `PromptText` protocol compatible with `typer.prompt`. Ask once for a
comma-separated subset of `title,body,base,reviewers`; reject unknown or empty
selections with `ValidationError`. Prompt selected text fields with current
values. For reviewers, prompt with existing login values and convert the final
list into add/remove tuples relative to the current raw reviewer identities.

- [ ] **Step 6: Verify GREEN and commit**

Run the new helper tests, then commit:

```bash
git add src/atlassian_cli/products/bitbucket/gh_compat/pr_edit.py \
  tests/products/bitbucket/test_gh_pr_edit.py
git commit -m "feat: add pull request edit input handling"
```

---

### Task 4: Wire the `pr edit` Command and Selector Exception

**Files:**
- Modify: `src/atlassian_cli/products/bitbucket/gh_compat/pr_finder.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Modify: `tests/products/bitbucket/test_gh_pr_finder.py`
- Create: `tests/products/bitbucket/test_pr_edit_command.py`

**Interfaces:**
- Consumes: repository resolution, `PullRequestFinder`, edit input helpers, and `PullRequestEditService`.
- Produces: public `atlassian bitbucket pr edit [selector]` command.

- [ ] **Step 1: Write the failing finder-exception test**

Add a test showing an omitted selector with `explicit_repo=True` resolves the
current branch only when `allow_explicit_repo_without_selector=True`. Keep the
existing view/checks failure test unchanged.

- [ ] **Step 2: Verify RED and add the opt-in finder parameter**

Add:

```python
def find(
    self,
    selector: str | None,
    resolution: RepositoryResolution,
    *,
    explicit_repo: bool,
    allow_explicit_repo_without_selector: bool = False,
) -> PullRequestRef:
```

Guard `selector is None and explicit_repo` only when the new flag is false.
Run all finder tests and expect them to pass.

- [ ] **Step 3: Write failing help and preflight command tests**

Assert help contains the exact usage and supported flags, omits every N03 flag,
and has no legacy project/repo positional arguments. Assert `--body` plus
`--body-file` exits `1` before provider or file access. Assert non-TTY with no
edit flags exits `1` before provider construction.

- [ ] **Step 4: Write failing orchestration tests**

Monkeypatch repository resolution, provider construction, finder, service, TTY
detection, and prompt adapter. Cover numeric, URL, branch, omitted current
branch, and omitted selector with `-R`; body file/stdin; repeated/comma reviewer
values; explicit empty title/body; prompt path; cancellation; host mismatch exit
`4`; service failure exit `1`; and success output containing only the PR URL.

- [ ] **Step 5: Implement `_edit_run` and the public command**

Register with `cls=GhReadCommand` so parser errors follow the migrated gh exit
policy. Use this shape:

```python
@app.command("edit", cls=GhReadCommand)
def edit_pull_request(
    ctx: typer.Context,
    selector: str | None = typer.Argument(None, metavar="[<number> | <url> | <branch>]"),
    add_reviewers: list[str] = typer.Option([], "--add-reviewer", metavar="login"),
    base: str | None = typer.Option(None, "--base", "-B", metavar="branch"),
    body: str | None = typer.Option(None, "--body", "-b"),
    body_file: str | None = typer.Option(None, "--body-file", "-F", metavar="file"),
    remove_reviewers: list[str] = typer.Option([], "--remove-reviewer", metavar="login"),
    repo: str | None = typer.Option(None, "--repo", "-R"),
    title: str | None = typer.Option(None, "--title", "-t"),
) -> None:
    run_gh_read(lambda: _edit_run(...))
```

In `_edit_run`, validate body-source conflict and non-TTY/no-flags before auth,
repository resolution, provider construction, and file reads. Resolve embedded
URL repositories, opt into the finder exception, load once for prompts, update
once, and print a deterministic Bitbucket web URL built from the selected ref.

- [ ] **Step 6: Verify GREEN**

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/python -m pytest -q \
  tests/products/bitbucket/test_gh_pr_finder.py \
  tests/products/bitbucket/test_gh_pr_edit.py \
  tests/products/bitbucket/test_pr_edit_command.py \
  tests/products/bitbucket/test_pr_edit_service.py \
  tests/products/bitbucket/test_pr_command.py
```

Expected: all focused PR tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/atlassian_cli/products/bitbucket/gh_compat/pr_finder.py \
  src/atlassian_cli/products/bitbucket/commands/pr.py \
  tests/products/bitbucket/test_gh_pr_finder.py \
  tests/products/bitbucket/test_pr_edit_command.py
git commit -m "feat: add gh-compatible Bitbucket PR editing"
```

---

### Task 5: Document and Live-Verify PR Editing

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Modify: `tests/e2e/coverage_manifest.py`
- Modify: `tests/e2e/test_bitbucket_live.py`

**Interfaces:**
- Consumes: public `bitbucket pr edit` command.
- Produces: durable user documentation and required live command ownership.

- [ ] **Step 1: Write failing README and manifest tests**

Extend `tests/test_readme.py` to require:

```text
atlassian bitbucket pr edit 1234 -R DEMO/example-repo --title "Example pull request"
atlassian bitbucket pr edit feature/DEMO-1234/example-change --body "example response"
```

Run the README test and `tests/e2e/test_coverage_manifest.py`; both must fail
before documentation/manifest changes.

- [ ] **Step 2: Update documentation and command ownership**

Add the two examples plus concise supported/unsupported field behavior to the
existing Bitbucket PR section. Add:

```python
"bitbucket pr edit": "test_bitbucket_branch_and_pr_round_trip_live",
```

to the coverage manifest.

- [ ] **Step 3: Extend the live PR round trip**

Immediately after PR creation/view, call:

```python
edited = run_cli(
    live_env,
    "bitbucket", "pr", "edit", str(pr_id),
    "-R", repo_selector,
    "--title", "Example pull request",
    "--body", "example response",
)
assert edited.returncode == 0, edited.stderr
assert edited.stdout.strip() == pr_url
```

Then fetch through `pr view --json number,title,body,url` and assert the exact
title, body, number, and URL. Keep the temporary PR/branch cleanup already owned
by the live test.

- [ ] **Step 4: Run focused local tests**

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/python -m pytest -q \
  tests/test_readme.py \
  tests/e2e/test_coverage_manifest.py \
  tests/products/bitbucket/test_pr_edit_command.py
```

Expected: all pass.

- [ ] **Step 5: Run required live e2e**

```bash
ATLASSIAN_E2E=1 PYTHONPATH="$PWD/src" \
  ../../.venv/bin/python -m pytest -q \
  tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live
```

Expected: pass against the configured Bitbucket Server/Data Center environment.
If unavailable, record the exact blocker and do not call the feature
live-verified.

- [ ] **Step 6: Scan public samples and commit**

```bash
rg -n -i 'agora|agoralab|NMS-|EEP-|@[A-Za-z0-9._%+-]+\.[A-Za-z]{2,}' \
  README.md tests/test_readme.py tests/e2e/coverage_manifest.py \
  tests/e2e/test_bitbucket_live.py \
  src/atlassian_cli/products/bitbucket tests/products/bitbucket
git diff --check
```

Normalize any non-functional real-looking value to the approved placeholder set,
then commit:

```bash
git add README.md tests/test_readme.py tests/e2e/coverage_manifest.py \
  tests/e2e/test_bitbucket_live.py
git commit -m "docs: document Bitbucket pull request editing"
```

---

### Task 6: Run Repository Quality Gates

**Files:**
- Verify all changed files.

**Interfaces:**
- Consumes: completed implementation.
- Produces: evidence for completion claims.

- [ ] **Step 1: Format changed Python files**

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/ruff format \
  src tests
```

- [ ] **Step 2: Run required format check**

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/ruff format --check .
```

- [ ] **Step 3: Run the full repository test suite**

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/python -m pytest -q
```

- [ ] **Step 4: Run the required Ruff lint scope**

```bash
PYTHONPATH="$PWD/src" ../../.venv/bin/ruff check \
  README.md pyproject.toml src tests docs
```

- [ ] **Step 5: Inspect final branch state**

```bash
git status --short --branch
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected: clean worktree, focused commits, all local quality gates passing, and
the feature-specific live result recorded separately.
