# Bitbucket GH Parity PR Read Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first useful GitHub CLI compatibility slice for Bitbucket Server 6.7.2: repository and pull-request selection, `pr list`/`ls`, `pr view`, the preserved `pr browse` workflow, and base `--json` output.

**Architecture:** Add only the read-only compatibility modules required by these commands. Pure selector parsing stays separate from Git/provider resolution; a focused PR read service performs field-driven enrichment; one output module owns GH human/JSON presentation; existing v0.1.19 services and renderers remain the compatibility path for hidden `--output` and `pr browse` fallback. Do not add mutation Git operations, a generic Git gateway, `--jq`/`--template`, or the Go formatter helper.

**Tech Stack:** Python 3.12+, Typer/Click, `atlassian-python-api`, stdlib `subprocess`/`urllib.parse`/`json`, pytest, ruff, and live e2e against Atlassian Bitbucket Server 6.7.2.

## Global Constraints

- Baselines are fixed at `gh v2.96.0` commit `b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0`, Bitbucket Server `6.7.2`, and existing CLI `v0.1.19` commit `2b5d8b2cedffda69fc963d83809186d9b5d62e79`.
- Implement only matrix rows needed by `pr list`, `pr view`, and `pr browse`; preserve their `M`, `D01`, `D06`, `B25`, `B30`, and `B31` classifications.
- `N03` fields/options stay absent from help and parsing. `--jq` and `--template` stay deferred even though the final spec maps them.
- Use `ATLASSIAN_BITBUCKET_REPO`, `ATLASSIAN_BROWSER`, `ATLASSIAN_PAGER`, `ATLASSIAN_PROMPT_DISABLED`, and optional `ATLASSIAN_FORCE_TTY`; do not read `GH_*` variables.
- Keep existing `pr get`, `pr build-status`, `pr approve`, and `pr unapprove` callable. Do not migrate `pr comment`, `pr diff`, `pr create`, or `pr merge` in this plan.
- Do not perform Git mutations, clone repositories, write Git config, or put credentials in subprocess arguments.
- All new examples and fixtures use repository-approved neutral placeholders only.
- Any changed CLI command must update unit tests, README, `tests/e2e/coverage_manifest.py` when a leaf is added, and the affected live e2e path.

## File Structure

- Create `tests/fixtures/gh-v2.96.0/bitbucket-pr-read-contract.json`
  - Stores sanitized grammar, field classifications, errors, and deterministic golden output.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/__init__.py`
  - Marks the compatibility package without exporting a broad facade.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/selectors.py`
  - Defines server/repository/PR references and pure selector parsing.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/repository_context.py`
  - Reads Git state without mutation and implements repository precedence.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/pr_finder.py`
  - Resolves numeric, URL, branch, and current-branch PR selectors.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/pr_output.py`
  - Validates JSON fields and renders base JSON plus `pr list`/`pr view` human output.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/io.py`
  - Owns D01 TTY, pager, and browser environment behavior.
- Create `src/atlassian_cli/products/bitbucket/gh_compat/exit_policy.py`
  - Applies GH exits only to migrated primary commands.
- Create `src/atlassian_cli/products/bitbucket/services/pr_read.py`
  - Implements filtering, pagination, canonical projection, and lazy enrichment.
- Modify `src/atlassian_cli/core/errors.py` and `src/atlassian_cli/auth/resolver.py`
  - Distinguish a missing configured credential without changing legacy exit mapping.
- Modify `src/atlassian_cli/products/bitbucket/providers/base.py` and `server.py`
  - Add only the PR activity/change/mergeability/dashboard reads required by this slice.
- Modify `src/atlassian_cli/products/bitbucket/commands/pr.py`
  - Wire primary `list`, hidden alias `ls`, `view`, `browse`, hidden legacy `--output`, and command-local GH parsing/exits.
- Modify `README.md`, `tests/e2e/coverage_manifest.py`, and `tests/e2e/test_bitbucket_live.py`
  - Document and live-cover the new forms and compatibility behavior.

---

### Task 1: Pin the First-Slice Oracle Contract

**Files:**
- Create: `tests/fixtures/gh-v2.96.0/bitbucket-pr-read-contract.json`
- Create: `tests/products/bitbucket/test_gh_pr_contract.py`

**Interfaces:**
- Consumes: approved design/matrix specs and the pinned `gh` source tests.
- Produces: one immutable test fixture used by command/output tests; no production interface.

- [ ] **Step 1: Add the sanitized contract fixture**

Create `tests/fixtures/gh-v2.96.0/bitbucket-pr-read-contract.json` with this exact content:

```json
{
  "baseline": {
    "bitbucket": "6.7.2",
    "gh": "2.96.0",
    "gh_commit": "b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0"
  },
  "commands": {
    "list": {
      "aliases": ["ls"],
      "default_limit": 30,
      "default_state": "open",
      "options": ["--author", "--base", "--head", "--json", "--limit", "--repo", "--search", "--state", "--web", "-A", "-B", "-H", "-L", "-R", "-S", "-s", "-w"],
      "state_values": ["open", "closed", "merged", "all"]
    },
    "view": {
      "options": ["--comments", "--json", "--repo", "--web", "-R", "-c", "-w"],
      "usage": "view [<number> | <url> | <branch>]"
    }
  },
  "blocked_json_fields": {
    "latestReviews": "B30",
    "mergeCommit": "B31",
    "potentialMergeCommit": "B25",
    "reviews": "B30"
  },
  "deferred_options": ["--jq", "--template", "-q", "-t"],
  "excluded_options": ["--app", "--assignee", "--draft", "--label"],
  "json_fields": [
    "additions", "author", "baseRefName", "baseRefOid", "body", "changedFiles",
    "closed", "closedAt", "comments", "commits", "createdAt", "deletions", "files",
    "fullDatabaseId", "headRefName", "headRefOid", "headRepository",
    "headRepositoryOwner", "id", "isCrossRepository", "latestReviews", "mergeCommit",
    "mergedAt", "mergedBy", "mergeable", "mergeStateStatus", "number",
    "potentialMergeCommit", "reviewDecision", "reviewRequests", "reviews", "state",
    "statusCheckRollup", "title", "updatedAt", "url"
  ],
  "errors": {
    "json_missing": "Specify one or more comma-separated fields for `--json`:",
    "json_unknown": "Unknown JSON field: \"unknownField\"",
    "web_json": "cannot use `--web` with `--json`",
    "view_repo_without_selector": "argument required when using the --repo flag",
    "blocked_reviews": "unsupported by Bitbucket Server 6.7.2: atomic pull-request review records (B30); required by gh v2.96.0 pr view --json reviews"
  },
  "golden": {
    "list_non_tty": "1234\tExample pull request\tfeature/DEMO-1234/example-change\tOPEN\t2026-07-15T12:00:00Z\n",
    "list_tty": "\nShowing 1 of 1 open pull request in DEMO/example-repo\n\nID     TITLE                 BRANCH                            CREATED AT\n#1234  Example pull request  feature/DEMO-1234/example-change  about 1 day ago\n",
    "view_non_tty": "title:\tExample pull request\nstate:\tOPEN\nauthor:\tExample Author\nlabels:\t\nassignees:\t\nreviewers:\treviewer-one (Requested)\nprojects:\t\nmilestone:\t\nnumber:\t1234\nurl:\thttps://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234\nadditions:\t1\ndeletions:\t0\nauto-merge:\tdisabled\n--\nexample response\n",
    "view_comments_non_tty": "author:\treviewer-one\nassociation:\tnone\nedited:\tfalse\nstatus:\tnone\n--\nexample comment\n--\n",
    "browser_notice": "Opening https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234 in your browser.\n"
  }
}
```

The golden strings retain GH's meaningful human layout. Empty GitHub-only metadata lines in non-TTY `view` are output placeholders, not invented Bitbucket data; N03 fields still remain unavailable to `--json`.

- [ ] **Step 2: Add fixture integrity tests**

Create `tests/products/bitbucket/test_gh_pr_contract.py`:

```python
import json
from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "gh-v2.96.0"
    / "bitbucket-pr-read-contract.json"
)


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text())


def test_pr_read_contract_has_fixed_baselines() -> None:
    assert load_contract()["baseline"] == {
        "bitbucket": "6.7.2",
        "gh": "2.96.0",
        "gh_commit": "b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0",
    }


def test_pr_read_contract_status_sets_are_consistent() -> None:
    contract = load_contract()
    accepted = set(contract["json_fields"])
    blocked = set(contract["blocked_json_fields"])
    assert len(accepted) == 36
    assert blocked <= accepted
    assert set(contract["excluded_options"]).isdisjoint(
        contract["commands"]["list"]["options"]
    )
    assert set(contract["deferred_options"]).isdisjoint(
        contract["commands"]["list"]["options"]
    )
    assert set(contract["deferred_options"]).isdisjoint(
        contract["commands"]["view"]["options"]
    )


def test_pr_read_contract_keeps_only_documented_blockers() -> None:
    assert load_contract()["blocked_json_fields"] == {
        "latestReviews": "B30",
        "mergeCommit": "B31",
        "potentialMergeCommit": "B25",
        "reviews": "B30",
    }


def test_web_and_json_match_the_pinned_oracle_conflict() -> None:
    assert load_contract()["errors"]["web_json"] == "cannot use `--web` with `--json`"
```

- [ ] **Step 3: Run and commit the contract fixture**

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_gh_pr_contract.py -q
git add tests/fixtures/gh-v2.96.0/bitbucket-pr-read-contract.json tests/products/bitbucket/test_gh_pr_contract.py
git commit -m "test: pin gh-compatible pull request read contract"
```

Expected: `4 passed`; the commit contains no production code.

---

### Task 2: Pure Selector Parsing

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/__init__.py`
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/selectors.py`
- Create: `tests/products/bitbucket/test_gh_selectors.py`

**Interfaces:**
- Consumes: configured Bitbucket base URL and user-supplied selector text.
- Produces: `ServerIdentity`, `RepositoryRef`, `PullRequestRef`, `RepositoryHostMismatchError`, `parse_repository_selector()`, and `parse_pull_request_url()`.

- [ ] **Step 1: Write failing selector tests**

Create `tests/products/bitbucket/test_gh_selectors.py` with every accepted repository form:

```python
import pytest

from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    PullRequestRef,
    RepositoryHostMismatchError,
    RepositoryRef,
    ServerIdentity,
    parse_pull_request_url,
    parse_repository_selector,
)


SERVER = ServerIdentity.from_url("https://bitbucket.example.com/bitbucket")


@pytest.mark.parametrize(
    ("value", "project", "repo"),
    [
        ("DEMO/example-repo", "DEMO", "example-repo"),
        ("bitbucket.example.com/DEMO/example-repo", "DEMO", "example-repo"),
        ("https://bitbucket.example.com/bitbucket/projects/DEMO/repos/example-repo", "DEMO", "example-repo"),
        ("https://bitbucket.example.com/bitbucket/scm/DEMO/example-repo.git", "DEMO", "example-repo"),
        ("ssh://git@bitbucket.example.com:7999/DEMO/example-repo.git", "DEMO", "example-repo"),
        ("git@bitbucket.example.com:DEMO/example-repo.git", "DEMO", "example-repo"),
        ("https://bitbucket.example.com/bitbucket/users/example-user/repos/example-repo", "~example-user", "example-repo"),
    ],
)
def test_parse_repository_selector(value: str, project: str, repo: str) -> None:
    assert parse_repository_selector(value, SERVER) == RepositoryRef(SERVER, project, repo)


def test_repository_selector_rejects_another_host() -> None:
    with pytest.raises(RepositoryHostMismatchError):
        parse_repository_selector(
            "https://other.example.com/scm/DEMO/example-repo.git",
            SERVER,
        )


def test_repository_selector_rejects_bare_repo_name() -> None:
    with pytest.raises(ValidationError, match="PROJECT/REPOSITORY"):
        parse_repository_selector("example-repo", SERVER)


def test_parse_pull_request_url_is_authoritative() -> None:
    value = "https://bitbucket.example.com/bitbucket/projects/DEMO/repos/example-repo/pull-requests/1234"
    assert parse_pull_request_url(value, SERVER) == PullRequestRef(
        RepositoryRef(SERVER, "DEMO", "example-repo"),
        1234,
    )
```

- [ ] **Step 2: Run the selector tests and verify failure**

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_gh_selectors.py -q
```

Expected: collection fails because the compatibility package does not exist.

- [ ] **Step 3: Implement the selector types and pure parsers**

Create an empty `gh_compat/__init__.py`. In `selectors.py`, implement these exact public types and keep URL matching ordered from specific web paths to generic clone paths so `/projects/.../repos/...` cannot be misread as `repos/example-repo`:

```python
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from atlassian_cli.core.errors import ValidationError


_SLUG_RE = re.compile(r"^[A-Za-z0-9._~-]+$")
_SCP_RE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+):(?P<path>.+)$")
_WEB_RE = re.compile(
    r"/(?:projects/(?P<project>[^/]+)|users/(?P<user>[^/]+))/repos/(?P<repo>[^/]+)(?:/|$)",
    re.IGNORECASE,
)
_PR_RE = re.compile(
    r"/(?:projects/(?P<project>[^/]+)|users/(?P<user>[^/]+))/repos/(?P<repo>[^/]+)/pull-requests/(?P<number>[0-9]+)(?:/|$)",
    re.IGNORECASE,
)


class RepositoryHostMismatchError(ValidationError):
    pass


@dataclass(frozen=True)
class ServerIdentity:
    scheme: str
    host: str
    port: int | None
    context_path: str

    @classmethod
    def from_url(cls, value: str) -> "ServerIdentity":
        parsed = urlparse(value.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValidationError(f"invalid Bitbucket server URL: {value}")
        return cls(parsed.scheme, parsed.hostname.lower(), parsed.port, parsed.path.rstrip("/"))

    @property
    def authority(self) -> str:
        return f"{self.host}:{self.port}" if self.port is not None else self.host

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.authority}{self.context_path}"

    def require_host(self, host: str | None, port: int | None, *, clone: bool = False) -> None:
        effective_port = port or ({"http": 80, "https": 443}.get(self.scheme))
        server_port = self.port or ({"http": 80, "https": 443}.get(self.scheme))
        if host is None or host.lower() != self.host or (not clone and effective_port != server_port):
            raise RepositoryHostMismatchError(
                "repository host does not match the configured Bitbucket server"
            )

    def strip_context_path(self, path: str) -> str:
        if not self.context_path:
            return path
        if path == self.context_path:
            return "/"
        prefix = self.context_path + "/"
        if not path.startswith(prefix):
            raise ValidationError("repository URL does not use the configured Bitbucket context path")
        return path[len(self.context_path):]


@dataclass(frozen=True)
class RepositoryRef:
    server: ServerIdentity
    project_key: str
    repo_slug: str

    @property
    def slug(self) -> str:
        return f"{self.project_key}/{self.repo_slug}"


@dataclass(frozen=True)
class PullRequestRef:
    repository: RepositoryRef
    number: int


def _repository(project: str, repo: str, server: ServerIdentity) -> RepositoryRef:
    project = unquote(project)
    repo = unquote(repo).removesuffix(".git")
    if not _SLUG_RE.fullmatch(project) or not _SLUG_RE.fullmatch(repo):
        raise ValidationError("repository must use PROJECT/REPOSITORY syntax")
    return RepositoryRef(server, project, repo)


def _web_or_clone(value: str, server: ServerIdentity) -> RepositoryRef | None:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "ssh"}:
        server.require_host(parsed.hostname, parsed.port, clone=parsed.scheme == "ssh")
        path = (
            parsed.path
            if parsed.scheme == "ssh"
            else server.strip_context_path(parsed.path)
        )
    elif match := _SCP_RE.fullmatch(value):
        server.require_host(match.group("host"), None, clone=True)
        path = "/" + match.group("path")
    else:
        return None
    if match := _WEB_RE.search(path):
        project = match.group("project") or f"~{match.group('user')}"
        return _repository(project, match.group("repo"), server)
    if match := re.search(r"/(?:scm/)?(?P<project>~?[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", path):
        return _repository(match.group("project"), match.group("repo"), server)
    raise ValidationError("repository must use PROJECT/REPOSITORY syntax")


def parse_repository_selector(value: str, server: ServerIdentity) -> RepositoryRef:
    value = value.strip()
    if parsed := _web_or_clone(value, server):
        return parsed
    parts = value.split("/")
    if len(parts) == 3:
        if parts[0].lower() != server.authority.lower():
            raise RepositoryHostMismatchError(
                "repository host does not match the configured Bitbucket server"
            )
        parts = parts[1:]
    if len(parts) != 2:
        raise ValidationError("repository must use PROJECT/REPOSITORY syntax")
    return _repository(parts[0], parts[1], server)


def parse_pull_request_url(value: str, server: ServerIdentity) -> PullRequestRef:
    parsed = urlparse(value)
    server.require_host(parsed.hostname, parsed.port)
    match = _PR_RE.search(server.strip_context_path(parsed.path))
    if match is None:
        raise ValidationError("invalid Bitbucket pull request URL")
    project = match.group("project") or f"~{match.group('user')}"
    return PullRequestRef(
        _repository(project, match.group("repo"), server),
        int(match.group("number")),
    )
```

Add tests for URL query/fragment tolerance, context paths, percent-decoded slugs, invalid PR URLs, and host-prefixed selectors. Parser functions must never access environment, Git, credentials, or providers.

- [ ] **Step 4: Run and commit selector parsing**

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_gh_selectors.py -q
git add src/atlassian_cli/products/bitbucket/gh_compat tests/products/bitbucket/test_gh_selectors.py
git commit -m "feat: parse gh-compatible Bitbucket selectors"
```

Expected: all selector cases pass.

---

### Task 3: Read-Only Git and Repository Resolution

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/repository_context.py`
- Create: `tests/products/bitbucket/test_gh_repository_context.py`

**Interfaces:**
- Consumes: `ServerIdentity`, explicit `-R`, `ATLASSIAN_BITBUCKET_REPO`, local Git remotes, and an optional TTY chooser.
- Produces: `GitRepositoryContext.read() -> GitRepositorySnapshot` and `RepositoryResolver.resolve() -> RepositoryResolution`.

- [ ] **Step 1: Write failing precedence and Git-safety tests**

Create `tests/products/bitbucket/test_gh_repository_context.py`:

```python
import subprocess

import pytest

from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.gh_compat.repository_context import (
    GitRepositoryContext,
    GitRepositorySnapshot,
    RepositoryResolver,
)
from atlassian_cli.products.bitbucket.gh_compat.selectors import RepositoryRef, ServerIdentity


SERVER = ServerIdentity.from_url("https://bitbucket.example.com")


def snapshot() -> GitRepositorySnapshot:
    return GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote="upstream",
        upstream_remote="origin",
        remotes={
            "origin": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
            "upstream": "ssh://git@bitbucket.example.com:7999/~example-user/example-repo.git",
        },
    )


def test_embedded_url_repo_beats_explicit_environment_and_git() -> None:
    resolver = RepositoryResolver(
        SERVER,
        snapshot(),
        env={"ATLASSIAN_BITBUCKET_REPO": "~example-user/example-repo"},
    )
    embedded = RepositoryRef(SERVER, "DEMO", "example-repo")
    assert resolver.resolve(
        explicit="~example-user/example-repo",
        embedded=embedded,
    ).repository == embedded


def test_explicit_beats_environment_and_git() -> None:
    resolver = RepositoryResolver(
        SERVER,
        snapshot(),
        env={"ATLASSIAN_BITBUCKET_REPO": "~example-user/example-repo"},
    )
    assert resolver.resolve(explicit="DEMO/example-repo").repository == RepositoryRef(
        SERVER, "DEMO", "example-repo"
    )


def test_default_remote_beats_branch_upstream_and_origin() -> None:
    result = RepositoryResolver(SERVER, snapshot(), env={}).resolve()
    assert result.repository == RepositoryRef(SERVER, "~example-user", "example-repo")


def test_non_tty_remote_ambiguity_lists_names() -> None:
    ambiguous = GitRepositorySnapshot(
        current_branch=None,
        default_remote=None,
        upstream_remote=None,
        remotes={
            "one": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
            "two": "https://bitbucket.example.com/scm/~example-user/example-repo.git",
        },
    )
    with pytest.raises(ValidationError, match="one, two"):
        RepositoryResolver(SERVER, ambiguous, env={}, can_prompt=False).resolve()


def test_tty_ambiguity_uses_injected_chooser() -> None:
    ambiguous = GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote=None,
        upstream_remote=None,
        remotes={
            "one": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
            "two": "https://bitbucket.example.com/scm/~example-user/example-repo.git",
        },
    )
    resolver = RepositoryResolver(
        SERVER,
        ambiguous,
        env={},
        can_prompt=True,
        choose_remote=lambda names: names[1],
    )
    assert resolver.resolve().repository.project_key == "~example-user"


def test_git_reader_runs_only_read_commands(tmp_path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", "https://bitbucket.example.com/scm/DEMO/example-repo.git"],
        check=True,
    )
    result = GitRepositoryContext(tmp_path).read()
    assert result.remotes == {
        "origin": "https://bitbucket.example.com/scm/DEMO/example-repo.git"
    }
    assert result.default_remote is None
```

- [ ] **Step 2: Run the repository-context tests and verify failure**

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_gh_repository_context.py -q
```

Expected: collection fails because `repository_context.py` does not exist.

- [ ] **Step 3: Implement the read-only snapshot and precedence**

Implement `GitRepositorySnapshot`, `RepositoryResolution`, and these read commands only:

```text
git remote
git remote get-url <name>
git symbolic-ref --quiet --short HEAD
git for-each-ref --format=%(upstream:remotename) refs/heads/<branch>
git config --get remote.<name>.atlassian-resolved
```

Use `subprocess.run(["git", *args], cwd=self.cwd, check=False, capture_output=True, text=True)` with no `shell=True`. `RepositoryResolver.resolve(*, explicit=None, embedded=None)` must implement this exact order:

```python
if embedded is not None:
    selected = embedded
elif explicit is not None:
    selected = parse_repository_selector(explicit, server)
elif env.get("ATLASSIAN_BITBUCKET_REPO"):
    selected = parse_repository_selector(env["ATLASSIAN_BITBUCKET_REPO"], server)
else:
    selected = first_valid(default_remote, upstream_remote, "origin")
    if selected is None:
        selected = only_match_or_tty_choice()
return RepositoryResolution(selected, git.current_branch)
```

`default_remote` is set only when exactly one remote has `remote.<name>.atlassian-resolved=base`. Ignore remotes whose URLs do not resolve to the configured server. A detached HEAD yields `current_branch=None`. Multiple valid remotes in non-TTY mode raise `multiple Bitbucket remotes match: one, two; use -R`; no valid source raises `unable to determine a Bitbucket repository; use -R`.

- [ ] **Step 4: Add command-capture and failure coverage**

Inject `RunGit = Callable[[list[str], Path], CompletedProcess[str]]` and assert the captured argument list contains no `clone`, `fetch`, config write, credentials, or shell strings. Add tests for invalid environment selectors, a foreign-host `origin`, multiple default markers, detached HEAD, and a single fallback remote.

- [ ] **Step 5: Run and commit repository resolution**

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_gh_selectors.py \
  tests/products/bitbucket/test_gh_repository_context.py -q
git add src/atlassian_cli/products/bitbucket/gh_compat/repository_context.py tests/products/bitbucket/test_gh_repository_context.py
git commit -m "feat: resolve Bitbucket repositories from local context"
```

Expected: all tests pass, including the real temporary-Git smoke test.

---

### Task 4: Pull Request Finder

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/pr_finder.py`
- Create: `tests/products/bitbucket/test_gh_pr_finder.py`

**Interfaces:**
- Consumes: `BitbucketProvider`, `ServerIdentity`, `RepositoryResolution`, and an optional PR selector.
- Produces: `PullRequestFinder.find(selector, resolution, explicit_repo=...) -> PullRequestRef`.

- [ ] **Step 1: Write failing numeric, URL, branch, and guard tests**

Create a fake provider that records `list_pull_requests()` calls, then add these cases to `tests/products/bitbucket/test_gh_pr_finder.py`:

```python
from datetime import UTC, datetime

import pytest

from atlassian_cli.core.errors import NotFoundError, ValidationError
from atlassian_cli.products.bitbucket.gh_compat.pr_finder import PullRequestFinder
from atlassian_cli.products.bitbucket.gh_compat.repository_context import RepositoryResolution
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    PullRequestRef,
    RepositoryRef,
    ServerIdentity,
)


SERVER = ServerIdentity.from_url("https://bitbucket.example.com")
REPO = RepositoryRef(SERVER, "DEMO", "example-repo")


def raw_pr(number: int, state: str, created: str, project: str, branch: str) -> dict:
    return {
        "id": number,
        "state": state,
        "createdDate": int(datetime.fromisoformat(created).replace(tzinfo=UTC).timestamp() * 1000),
        "fromRef": {
            "displayId": branch,
            "repository": {"slug": "example-repo", "project": {"key": project}},
        },
    }


class FakeProvider:
    def __init__(self, pages: dict[tuple[str, int], list[dict]] | None = None) -> None:
        self.pages = pages or {}
        self.calls: list[tuple] = []

    def list_pull_requests(self, project, repo, state, *, start, limit):
        self.calls.append((project, repo, state, start, limit))
        return self.pages.get((state, start), [])


def resolution(branch: str | None = "feature/DEMO-1234/example-change") -> RepositoryResolution:
    return RepositoryResolution(REPO, branch)


def test_numeric_selector_uses_resolved_repository_without_listing() -> None:
    provider = FakeProvider()
    result = PullRequestFinder(provider, SERVER).find("1234", resolution(), explicit_repo=False)
    assert result == PullRequestRef(REPO, 1234)
    assert provider.calls == []


def test_url_selector_is_authoritative_over_resolved_repository() -> None:
    selected = RepositoryRef(SERVER, "~example-user", "example-repo")
    url = "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"
    result = PullRequestFinder(FakeProvider(), SERVER).find(
        url,
        RepositoryResolution(selected, None),
        explicit_repo=True,
    )
    assert result == PullRequestRef(REPO, 1234)


def test_view_repo_without_selector_fails_before_current_branch_lookup() -> None:
    provider = FakeProvider()
    with pytest.raises(ValidationError, match="argument required when using the --repo flag"):
        PullRequestFinder(provider, SERVER).find(None, resolution(), explicit_repo=True)
    assert provider.calls == []


def test_branch_ranks_open_before_newer_closed_then_newest_open() -> None:
    provider = FakeProvider(
        {
            ("OPEN", 0): [
                raw_pr(1233, "OPEN", "2026-07-14T12:00:00", "DEMO", "feature/DEMO-1234/example-change"),
                raw_pr(1234, "OPEN", "2026-07-15T12:00:00", "DEMO", "feature/DEMO-1234/example-change"),
            ],
            ("DECLINED", 0): [
                raw_pr(1235, "DECLINED", "2026-07-16T12:00:00", "DEMO", "feature/DEMO-1234/example-change")
            ],
        }
    )
    result = PullRequestFinder(provider, SERVER).find(
        "feature/DEMO-1234/example-change",
        resolution(),
        explicit_repo=False,
    )
    assert result.number == 1234


def test_qualified_branch_requires_exact_source_project() -> None:
    provider = FakeProvider(
        {
            ("OPEN", 0): [
                raw_pr(1234, "OPEN", "2026-07-15T12:00:00", "DEMO", "feature/DEMO-1234/example-change"),
                raw_pr(1235, "OPEN", "2026-07-16T12:00:00", "~example-user", "feature/DEMO-1234/example-change"),
            ]
        }
    )
    result = PullRequestFinder(provider, SERVER).find(
        "~example-user:feature/DEMO-1234/example-change",
        resolution(),
        explicit_repo=False,
    )
    assert result.number == 1235


def test_detached_head_without_selector_is_not_found() -> None:
    with pytest.raises(NotFoundError, match="current branch"):
        PullRequestFinder(FakeProvider(), SERVER).find(
            None,
            resolution(None),
            explicit_repo=False,
        )
```

- [ ] **Step 2: Run finder tests and verify failure**

```bash
.venv/bin/python -m pytest tests/products/bitbucket/test_gh_pr_finder.py -q
```

Expected: collection fails because `pr_finder.py` does not exist.

- [ ] **Step 3: Implement the finder without adding a second service layer**

Implement one `PullRequestFinder` class. Numeric and URL selectors return immediately. Omitted selectors use `resolution.current_branch` only when `explicit_repo` is false. Branch lookup pages `OPEN`, `DECLINED`, and `MERGED` at 100 records per request, deduplicates by PR ID, requires an exact source project/repository/ref match, and ranks with this key:

```python
def _rank(raw: dict) -> tuple[int, int, int]:
    return (
        1 if raw.get("state") == "OPEN" else 0,
        int(raw.get("createdDate") or 0),
        int(raw.get("id") or 0),
    )
```

The core implementation must follow this control flow:

```python
def find(
    self,
    selector: str | None,
    resolution: RepositoryResolution,
    *,
    explicit_repo: bool,
) -> PullRequestRef:
    if selector and "://" in selector:
        return parse_pull_request_url(selector, self.server)
    if selector is None and explicit_repo:
        raise ValidationError("argument required when using the --repo flag")
    if selector is None:
        selector = resolution.current_branch
        if selector is None:
            raise NotFoundError("no pull request found for the current branch")
    if selector.isdecimal():
        number = int(selector)
        if number < 1:
            raise ValidationError("pull request number must be greater than zero")
        return PullRequestRef(resolution.repository, number)
    project, branch = self._split_branch(selector, resolution.repository.project_key)
    matches = [
        raw
        for raw in self._all_candidates(resolution.repository)
        if self._matches(raw, project, resolution.repository.repo_slug, branch)
    ]
    if not matches:
        raise NotFoundError(f"no pull request found for branch {selector}")
    selected = max(matches, key=_rank)
    return PullRequestRef(resolution.repository, int(selected["id"]))
```

`_split_branch()` splits only the first `:` and treats `PROJECT:branch` as qualified only when both sides are nonblank. `_all_candidates()` stops a state when a page returns fewer than 100 items. It performs no `get_pull_request()` enrichment and no mutation.

- [ ] **Step 4: Cover pagination, duplicate IDs, and zero-match behavior**

Add a two-page test where page zero has 100 nonmatching records and page 100 has the matching PR; assert the exact `start` values. Add a duplicate ID returned by two state queries and assert ranking only considers it once. Assert zero matches raise `NotFoundError` and never fall back to a fuzzy ref comparison.

- [ ] **Step 5: Run and commit the finder**

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_gh_repository_context.py \
  tests/products/bitbucket/test_gh_pr_finder.py -q
git add src/atlassian_cli/products/bitbucket/gh_compat/pr_finder.py tests/products/bitbucket/test_gh_pr_finder.py
git commit -m "feat: resolve Bitbucket pull request selectors"
```

Expected: all repository/finder tests pass.

---

### Task 5: Provider Reads and Field-Driven PR Read Service

**Files:**
- Modify: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Create: `src/atlassian_cli/products/bitbucket/services/pr_read.py`
- Modify: `tests/products/bitbucket/test_provider.py`
- Create: `tests/products/bitbucket/test_pr_read_service.py`

**Interfaces:**
- Consumes: `BitbucketProvider`, `RepositoryRef`, `PullRequestRef`, list filters, and requested output fields.
- Produces: `PullRequestListFilters`, `PullRequestListResult`, `PullRequestReadService.list() -> PullRequestListResult`, and `PullRequestReadService.get() -> dict` using the canonical GH-compatible projection.

- [ ] **Step 1: Add failing provider primitive tests**

Extend `tests/products/bitbucket/test_provider.py` with fake-client assertions for exactly four new read primitives:

```python
def test_bitbucket_provider_exposes_pr_read_primitives() -> None:
    calls = {}

    class FakeClient:
        def get_pull_requests_activities(self, project, repo, pr_id, start=0, limit=None):
            calls["activities"] = (project, repo, pr_id, start, limit)
            return {"values": [{"action": "MERGED"}]}

        def get_pull_requests_changes(self, project, repo, pr_id, start=0, limit=None):
            calls["changes"] = (project, repo, pr_id, start, limit)
            return {"values": [{"type": "ADD", "path": {"toString": "example.py"}}]}

        def is_pull_request_can_be_merged(self, project, repo, pr_id):
            calls["mergeability"] = (project, repo, pr_id)
            return {"canMerge": True, "conflicted": False, "vetoes": []}

        def get_dashboard_pull_requests(self, start=0, limit=None, role=None, state=None, order=None):
            calls["dashboard"] = (start, limit, role, state, order)
            return {"values": [{"id": 1234}]}

    provider = build_provider_with_client(FakeClient())
    assert provider.list_pull_request_activities("DEMO", "example-repo", 1234, start=0, limit=100)
    assert provider.list_pull_request_changes("DEMO", "example-repo", 1234, start=0, limit=100)
    assert provider.get_pull_request_mergeability("DEMO", "example-repo", 1234)["canMerge"]
    assert provider.list_dashboard_pull_requests(
        role="AUTHOR", state="OPEN", start=0, limit=100
    ) == [{"id": 1234}]
    assert calls == {
        "activities": ("DEMO", "example-repo", 1234, 0, 100),
        "changes": ("DEMO", "example-repo", 1234, 0, 100),
        "mergeability": ("DEMO", "example-repo", 1234),
        "dashboard": (0, 100, "AUTHOR", "OPEN", "NEWEST"),
    }
```

- [ ] **Step 2: Implement only those provider reads**

Add these signatures to `BitbucketProvider` and implement them in `BitbucketServerProvider` through the existing SDK client and `_paged_items()`:

```python
def list_pull_request_activities(
    self, project_key: str, repo_slug: str, pr_id: int, *, start: int, limit: int
) -> list[dict]: ...

def list_pull_request_changes(
    self, project_key: str, repo_slug: str, pr_id: int, *, start: int, limit: int
) -> list[dict]: ...

def get_pull_request_mergeability(
    self, project_key: str, repo_slug: str, pr_id: int
) -> dict: ...

def list_dashboard_pull_requests(
    self, *, role: str, state: str, start: int, limit: int
) -> list[dict]: ...
```

The server adapter calls `get_pull_requests_activities`, `get_pull_requests_changes`, `is_pull_request_can_be_merged`, and `get_dashboard_pull_requests(order="NEWEST")`. Do not expose SDK client internals to the service and do not add mutation methods.

- [ ] **Step 3: Write failing direct-projection and lazy-enrichment tests**

Create `tests/products/bitbucket/test_pr_read_service.py` with a fake provider whose methods append names to `calls`. Use a raw PR containing only approved sample data, then assert:

```python
def test_basic_list_fields_do_not_trigger_auxiliary_reads() -> None:
    provider = FakeProvider([raw_pr()])
    service = PullRequestReadService(provider)
    result = service.list(
        REPO,
        PullRequestListFilters(state="open", limit=30),
        fields={"number", "title", "state", "url", "headRefName", "createdAt"},
    )
    assert result.items[0] == {
        "number": 1234,
        "title": "Example pull request",
        "state": "OPEN",
        "url": "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234",
        "headRefName": "feature/DEMO-1234/example-change",
        "createdAt": "2026-07-15T12:00:00Z",
    }
    assert provider.auxiliary_calls == []


def test_requested_enrichments_call_each_provider_family_once() -> None:
    provider = FakeProvider([raw_pr()])
    result = PullRequestReadService(provider).get(
        PullRequestRef(REPO, 1234),
        fields={
            "additions", "changedFiles", "comments", "commits", "deletions", "files",
            "mergeable", "mergeStateStatus", "mergedAt", "mergedBy", "statusCheckRollup",
        },
    )
    assert result["additions"] == 1
    assert result["deletions"] == 0
    assert result["changedFiles"] == 1
    assert result["mergeable"] == "MERGEABLE"
    assert result["mergeStateStatus"] == "CLEAN"
    assert result["statusCheckRollup"][0]["__typename"] == "StatusContext"
    assert provider.auxiliary_calls == [
        "changes", "diff", "activities", "commits", "mergeability", "builds"
    ]
```

Also assert a request for one field returns only that property and never fetches enrichments for unrequested fields. Task 6 owns deterministic lexicographic JSON key ordering, matching Go's `encoding/json` map output. Add one TTY-count case that sets `count_total=True`, returns 30 items plus the complete matched count, and proves paging continues after the 30th item only to compute that count.

- [ ] **Step 4: Define the canonical direct mapping in `pr_read.py`**

Add one request and one result dataclass:

```python
@dataclass(frozen=True)
class PullRequestListFilters:
    state: str = "open"
    limit: int = 30
    author: str | None = None
    base: str | None = None
    head: str | None = None
    search: str | None = None


@dataclass(frozen=True)
class PullRequestListResult:
    items: list[dict]
    total_count: int | None
```

Implement `PullRequestReadService(provider)` with `list(repository, filters, fields, *, count_total=False)` and `get(ref, fields)`. The direct projection is exact:

```python
direct = {
    "author": user(raw.get("author", {}).get("user")),
    "baseRefName": raw["toRef"].get("displayId"),
    "baseRefOid": raw["toRef"].get("latestCommit"),
    "body": raw.get("description") or "",
    "closed": raw.get("state") != "OPEN",
    "closedAt": closed_at(raw),
    "createdAt": rfc3339(raw.get("createdDate")),
    "fullDatabaseId": str(raw["id"]),
    "headRefName": raw["fromRef"].get("displayId"),
    "headRefOid": raw["fromRef"].get("latestCommit"),
    "headRepository": repository_object(raw["fromRef"].get("repository")),
    "headRepositoryOwner": project_object(raw["fromRef"].get("repository")),
    "id": str(raw["id"]),
    "isCrossRepository": repository_identity(raw["fromRef"]) != repository_identity(raw["toRef"]),
    "number": int(raw["id"]),
    "reviewDecision": review_decision(raw.get("reviewers", [])),
    "reviewRequests": review_requests(raw.get("reviewers", [])),
    "state": {"OPEN": "OPEN", "DECLINED": "CLOSED", "MERGED": "MERGED"}[raw["state"]],
    "title": raw.get("title") or "",
    "updatedAt": rfc3339(raw.get("updatedDate")),
    "url": first_self_link(raw),
}
```

`user(raw_user)` returns `{"id": str(raw_user["id"]), "is_bot": False, "login": raw_user["name"], "name": raw_user["displayName"]}` with `None` for a missing user and `slug` fallbacks for missing keys. `repository_object()` returns `id`, `name`, and `nameWithOwner`; `project_object()` returns `id`, `login`, and `name`. Dates convert Bitbucket epoch milliseconds to UTC RFC3339 seconds. `closedAt` is `None` for OPEN and otherwise uses `closedDate`, then `updatedDate`.

- [ ] **Step 5: Implement enrichment groups, not one function per JSON field**

Use these field groups so one REST family is fetched once:

```python
DIFF_FIELDS = {"additions", "changedFiles", "deletions", "files"}
ACTIVITY_FIELDS = {"comments", "mergedAt", "mergedBy"}
COMMIT_FIELDS = {"commits"}
MERGEABILITY_FIELDS = {"mergeable", "mergeStateStatus"}
BUILD_FIELDS = {"statusCheckRollup"}
```

Page changes, activities, and commits at 100 items until a short page. Combine `/changes` paths/types with the existing line-aware diff payload: `ADDED` lines increment additions, `REMOVED` lines increment deletions, and file `changeType` maps `ADD -> ADDED`, `DELETE -> DELETED`, `MOVE -> RENAMED`, `COPY -> COPIED`, otherwise `MODIFIED`.

Map enriched objects as follows:

```python
comment = {
    "id": str(raw_comment["id"]),
    "url": raw_comment.get("links", {}).get("self", [{}])[0].get("href", ""),
    "body": raw_comment.get("text") or "",
    "author": user(raw_comment.get("author")),
    "authorAssociation": "NONE",
    "createdAt": rfc3339(raw_comment.get("createdDate")),
    "updatedAt": rfc3339(raw_comment.get("updatedDate")),
}

message_lines = (raw_commit.get("message") or "").splitlines()
commit = {
    "oid": raw_commit.get("id"),
    "messageHeadline": message_lines[0] if message_lines else "",
    "messageBody": "\n".join(message_lines[1:]),
    "authoredDate": rfc3339(raw_commit.get("authorTimestamp")),
    "committedDate": rfc3339(raw_commit.get("committerTimestamp")),
    "authors": [user(raw_commit.get("author"))],
}

status_context = {
    "__typename": "StatusContext",
    "context": raw_build.get("key") or "",
    "state": normalize_build_state(raw_build.get("state")),
    "targetUrl": raw_build.get("url") or "",
    "startedAt": rfc3339(raw_build.get("dateAdded")),
}
```

Reconstruct current comments from activities in chronological order: `ADDED` and `UPDATED` replace the entry by comment ID, `DELETED` removes it, and non-comment activities are ignored. Emit remaining comments by creation time so update/delete events never duplicate stale bodies. For mergeability, `canMerge=true` yields `MERGEABLE/CLEAN`; `conflicted=true` yields `CONFLICTING/DIRTY`; nonempty vetoes yield `UNKNOWN/BLOCKED`; otherwise `UNKNOWN/UNKNOWN`. Find the newest `MERGED` activity for `mergedAt`/`mergedBy`. `statusCheckRollup` reads only the resolved head SHA and returns `[]` when the build endpoint has no values.

- [ ] **Step 6: Implement paging and mapped search filters**

Map states as `open -> OPEN`, `closed -> DECLINED`, `merged -> MERGED`, and `all -> ALL`. Fetch server-ordered pages, deduplicate IDs, and apply filters before the limit. With `count_total=False`, stop after `limit` matches; with `count_total=True`, keep paging to exhaustion and retain only the first `limit` items while counting all matches. Reject `limit < 1` before provider calls. The command uses `count_total=True` only for TTY human list output because Bitbucket 6.7.2 pages have no total; JSON and non-TTY output stop at the requested limit.

Parse `--search` with `shlex.split()`. Treat bare terms as case-insensitive title/body terms and honor `in:title`, `in:body`, or the default both-fields scope. Support `state:`/`is:`, `author:`, `base:`, `head:`, `review:none|required|approved|changes_requested`, and `status:pending|success|failure`; a leading `-` negates mapped predicates. Explicit `--author`, `--base`, and `--head` combine with search qualifiers. Any search state clause replaces only the default `open` state by fetching `ALL` and applying the positive/negative state predicates locally; an explicitly nondefault `--state` remains an additional predicate, matching the pinned command's default-state override rule. Contradictory predicates yield an empty result without weakening either clause. Reject known N03 qualifiers `assignee`, `draft`, `label`, `milestone`, `project`, `app`, and `team`, including negated forms, before provider calls. `author:@me` uses `list_dashboard_pull_requests(role="AUTHOR", ...)` and filters those results to the resolved repository; it does not guess the token owner's username.

Add tests for state mapping, filter combinations, quoted text and `in:` scopes, positive/negative qualifiers, `@me`, search state override, contradictory state yielding no result, status enrichment only when required, pagination after filtering, stable ordering, and all N03 qualifier rejections.

- [ ] **Step 7: Run and commit provider/read service**

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_provider.py \
  tests/products/bitbucket/test_pr_read_service.py -q
git add \
  src/atlassian_cli/products/bitbucket/providers/base.py \
  src/atlassian_cli/products/bitbucket/providers/server.py \
  src/atlassian_cli/products/bitbucket/services/pr_read.py \
  tests/products/bitbucket/test_provider.py \
  tests/products/bitbucket/test_pr_read_service.py
git commit -m "feat: project Bitbucket pull request read data"
```

Expected: provider and service suites pass; fake call logs prove lazy enrichment and zero mutation.

---

### Task 6: GH Output and Product-Prefixed IO

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/pr_output.py`
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/io.py`
- Create: `tests/products/bitbucket/test_gh_pr_output.py`
- Create: `tests/products/bitbucket/test_gh_io.py`

**Interfaces:**
- Consumes: canonical dictionaries from `PullRequestReadService`, one or more requested JSON field strings, TTY state, environment, and URLs.
- Produces: `validate_json_fields()`, `render_json()`, `render_pr_list()`, `render_pr_view()`, `stdout_is_tty()`, `can_prompt()`, `page_output()`, and `open_browser()`.

- [ ] **Step 1: Write failing JSON preflight and serialization tests**

In `tests/products/bitbucket/test_gh_pr_output.py`, load Task 3's contract fixture and cover validation before any service call:

```python
import pytest

from atlassian_cli.products.bitbucket.gh_compat.pr_output import (
    GhPreflightError,
    MISSING_JSON_VALUE,
    render_json,
    validate_json_fields,
)


def test_json_without_value_lists_sorted_fields() -> None:
    with pytest.raises(GhPreflightError) as exc:
        validate_json_fields(MISSING_JSON_VALUE, web=False, surface="pr list")
    message = str(exc.value)
    assert message.startswith("Specify one or more comma-separated fields for `--json`:\n")
    assert "  additions\n  author\n" in message


def test_web_json_conflict_precedes_repository_resolution() -> None:
    with pytest.raises(GhPreflightError, match="cannot use `--web` with `--json`"):
        validate_json_fields("number", web=True, surface="pr list")


def test_unknown_field_lists_available_fields() -> None:
    with pytest.raises(GhPreflightError, match='Unknown JSON field: "unknownField"'):
        validate_json_fields("unknownField", web=False, surface="pr view")


def test_blocked_field_is_accepted_then_fails_capability_preflight() -> None:
    with pytest.raises(GhPreflightError, match="Bitbucket Server 6.7.2.*B30"):
        validate_json_fields("reviews", web=False, surface="pr view")


def test_non_tty_json_is_compact_sorted_and_newline_terminated() -> None:
    value = {"title": "Example pull request", "number": 1234}
    assert render_json(value, color=False) == (
        '{"number":1234,"title":"Example pull request"}\n'
    )


def test_tty_json_matches_gh_jsoncolor() -> None:
    assert render_json({"number": 1234}, color=True) == (
        "\x1b[1;37m{\x1b[m\n"
        "  \x1b[1;34m\"number\"\x1b[m\x1b[1;37m:\x1b[m 1234\n"
        "\x1b[1;37m}\x1b[m\n"
    )
```

The capability error uses the normative form plus the blocker code, for example `unsupported by Bitbucket Server 6.7.2: atomic pull-request review records (B30); required by gh v2.96.0 pr view --json reviews`.

- [ ] **Step 2: Implement JSON preflight and the small Python jsoncolor writer**

In `pr_output.py`, define a small `GhPreflightError(AtlassianCliError)` whose message must be written verbatim, `JSON_FIELDS` from the fixture's 36-field list in production code, `BLOCKED_FIELDS` with capability text, and a sentinel string used only by command argv normalization:

```python
MISSING_JSON_VALUE = "__ATLASSIAN_MISSING_JSON_VALUE__"

BLOCKED_FIELDS = {
    "latestReviews": ("B30", "atomic pull-request review records"),
    "reviews": ("B30", "atomic pull-request review records"),
    "mergeCommit": ("B31", "pull-request merge-commit identity"),
    "potentialMergeCommit": ("B25", "potential merge commit"),
}
```

`validate_json_fields(value: str | Sequence[str] | None, *, web, surface)` accepts comma-separated and repeated `--json` values. It must apply this order: omitted option returns `None`; any missing-value sentinel raises `GhPreflightError` with the sorted allowed list; any present JSON value plus `web` raises the pinned conflict; unknown fields include the sorted allowed list; blocked fields use the normative capability text; successful fields return a deduplicated tuple. All failure branches use `GhPreflightError` and run before repository or provider construction.

For JSON output, call `json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)`. Non-color output adds one newline. The color path recursively emits the pinned `gh` ANSI constants without pulling in the optional Go helper:

```python
COLOR_DELIM = "1;37"
COLOR_KEY = "1;34"
COLOR_NULL = "36"
COLOR_STRING = "32"
COLOR_BOOL = "33"
```

Indent nested objects and arrays by two spaces, color keys/delimiters/strings/null/bools exactly like `pkg/jsoncolor/jsoncolor.go` at the pinned `gh` commit, leave numbers uncolored, and always end with one newline.

- [ ] **Step 3: Write failing list/view human-output tests**

Use a fixed `now=datetime(2026, 7, 16, 12, tzinfo=UTC)` and the golden fixture:

```python
def test_list_non_tty_matches_golden(contract, canonical_pr) -> None:
    assert render_pr_list(
        [canonical_pr],
        repository="DEMO/example-repo",
        total=1,
        filtered=False,
        tty=False,
        color=False,
        now=NOW,
    ) == contract["golden"]["list_non_tty"]


def test_list_tty_matches_golden(contract, canonical_pr) -> None:
    assert strip_ansi(render_pr_list(
        [canonical_pr],
        repository="DEMO/example-repo",
        total=1,
        filtered=False,
        tty=True,
        color=True,
        now=NOW,
    )) == contract["golden"]["list_tty"]


def test_view_non_tty_matches_golden(contract, canonical_pr) -> None:
    assert render_pr_view(
        canonical_pr,
        repository="DEMO/example-repo",
        tty=False,
        color=False,
        comments=False,
        now=NOW,
    ) == contract["golden"]["view_non_tty"]


def test_view_comments_non_tty_outputs_only_raw_comments(contract, canonical_pr) -> None:
    assert render_pr_view(
        canonical_pr,
        repository="DEMO/example-repo",
        tty=False,
        color=False,
        comments=True,
        now=NOW,
    ) == contract["golden"]["view_comments_non_tty"]
```

Add TTY assertions for title/repository/number, state/author/ref summary, additions/deletions, check summary, reviewer state, Markdown body, comment preview versus full `--comments`, and the Bitbucket footer. In non-TTY human mode, `--comments` emits only the raw chronological comment blocks shown in the golden fixture, matching the pinned `viewRun` branch; it does not prepend PR detail. JSON and web modes still take precedence over this flag. Empty `pr list` raises `no open pull requests in DEMO/example-repo` or `no pull requests match your search in DEMO/example-repo`, exit-classified later as `1`.

- [ ] **Step 4: Implement list/view presenters without a general rendering framework**

`render_pr_list()` owns only four columns. TTY output has the `Showing ...` header, `#` IDs, no STATE column, fuzzy time, and state/branch colors; non-TTY output is tab-separated with numeric IDs, STATE, and RFC3339 created time. Collapse title whitespace and compute stable column widths from headers plus rows.

`render_pr_view()` follows the pinned paths:

```text
TTY:
  Example pull request DEMO/example-repo#1234
  Open • Example Author wants to merge 1 commit into main from feature/DEMO-1234/example-change • about 1 day ago
  +1 -0 • No checks
  Reviewers: reviewer-one (Requested)

  example response

  View this pull request in Bitbucket: https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234

non-TTY:
  title/state/author/labels/assignees/reviewers/projects/milestone/number/url/
  additions/deletions/auto-merge, then -- and the raw body
```

Use Rich's already-installed Markdown renderer only for the TTY body, with an injected width and captured console for tests. Do not add a reusable page/component abstraction. Map reviewer states `APPROVED -> Approved`, `NEEDS_WORK -> Changes requested`, and all other reviewers to `Requested`.

- [ ] **Step 5: Write failing D01 IO precedence tests**

Create `tests/products/bitbucket/test_gh_io.py`:

```python
from subprocess import CompletedProcess


def test_force_tty_uses_only_atlassian_namespace() -> None:
    assert stdout_is_tty(lambda: False, {"ATLASSIAN_FORCE_TTY": "1"}) is True
    assert stdout_is_tty(lambda: False, {"GH_FORCE_TTY": "1"}) is False


def test_prompt_requires_both_streams_and_honors_product_namespace() -> None:
    assert can_prompt(lambda: True, lambda: True, {}) is True
    assert can_prompt(
        lambda: True,
        lambda: True,
        {"ATLASSIAN_PROMPT_DISABLED": ""},
    ) is False
    assert can_prompt(
        lambda: True,
        lambda: True,
        {"GH_PROMPT_DISABLED": "1"},
    ) is True


def test_browser_precedence_appends_url_without_shell() -> None:
    calls = []
    open_browser(
        "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234",
        env={"ATLASSIAN_BROWSER": "echo --new-window", "BROWSER": "echo --fallback"},
        run=lambda args: calls.append(args) or CompletedProcess(args, 0),
    )
    assert calls == [[
        "echo",
        "--new-window",
        "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234",
    ]]


def test_pager_precedence_writes_content_to_stdin() -> None:
    calls = []
    page_output(
        "example response\n",
        tty=True,
        env={"ATLASSIAN_PAGER": "cat -n", "PAGER": "cat"},
        error_prefix="error starting pager",
        run=lambda args, text: calls.append((args, text)) or CompletedProcess(args, 0),
    )
    assert calls == [(["cat", "-n"], "example response\n")]
```

- [ ] **Step 6: Implement small IO functions with standard fallbacks**

`stdout_is_tty()` returns true when the stream is a TTY or `ATLASSIAN_FORCE_TTY` is present with a nonempty value. `can_prompt()` requires stdin plus effective stdout TTY and returns false whenever `ATLASSIAN_PROMPT_DISABLED` is present, even with an empty value. `color_enabled()` also honors `NO_COLOR` and `CLICOLOR=0`. `open_browser()` uses `ATLASSIAN_BROWSER`, then `BROWSER`, then `webbrowser.open`; configured commands are split with `shlex.split`, receive the URL as the last argv element, and run without a shell. `page_output(text, *, tty, env, error_prefix, run, stdout, stderr)` writes directly when non-TTY; in TTY it uses `ATLASSIAN_PAGER`, then `PAGER`, then `less -FRX` when available. On pager startup failure, write `f"{error_prefix}: {error}"` to stderr and then write the content directly. Primary list passes `error starting pager`; primary view passes `failed to start pager`, matching the pinned source. None of these functions reads any `GH_*` key.

For browser commands, replace `%s` inside an argv token when present; append the URL only when no placeholder exists. Empty product-prefixed values fall through to the standard variable. Add tests for `%s`, empty-value fallback, browser launch failure, pager startup failure, and direct non-TTY writes.

- [ ] **Step 7: Run and commit output/IO**

```bash
.venv/bin/python -m pytest \
  tests/products/bitbucket/test_gh_pr_output.py \
  tests/products/bitbucket/test_gh_io.py -q
git add \
  src/atlassian_cli/products/bitbucket/gh_compat/pr_output.py \
  src/atlassian_cli/products/bitbucket/gh_compat/io.py \
  tests/products/bitbucket/test_gh_pr_output.py \
  tests/products/bitbucket/test_gh_io.py
git commit -m "feat: render gh-compatible pull request reads"
```

Expected: output matches the sanitized oracle fixture in TTY/non-TTY and color/non-color modes.

---

### Task 7: Command Wiring, Compatibility, and GH Exit Policy

**Files:**
- Modify: `src/atlassian_cli/core/errors.py`
- Modify: `src/atlassian_cli/auth/resolver.py`
- Create: `src/atlassian_cli/products/bitbucket/gh_compat/exit_policy.py`
- Modify: `src/atlassian_cli/products/bitbucket/commands/pr.py`
- Modify: `tests/auth/test_headers.py`
- Modify: `tests/products/bitbucket/test_pr_command.py`
- Modify: `tests/test_cli_help.py`

**Interfaces:**
- Consumes: selector/resolver/finder/read-service/output/IO interfaces from Tasks 1-6 and existing v0.1.19 `PullRequestService`/browser/renderers.
- Produces: primary `pr list`, hidden callable `pr ls`, primary `pr view`, compatibility `pr browse`, hidden legacy list `--output`, and GH exits isolated to migrated commands.

- [ ] **Step 1: Add failing help, grammar, preflight-order, and compatibility tests**

Replace the old `pr list` command expectations in `tests/products/bitbucket/test_pr_command.py` and extend `tests/test_cli_help.py`. The required cases are:

```python
def test_pr_list_help_matches_first_slice() -> None:
    result = runner.invoke(app, ["bitbucket", "pr", "list", "--help"], env=ci_output_env())
    output = strip_ansi(result.output)
    assert result.exit_code == 0
    for option in ("--author", "--base", "--head", "--json", "--limit", "--repo", "--search", "--state", "--web"):
        assert option in output
    for absent in ("--app", "--assignee", "--draft", "--label", "--jq", "--template", "--output"):
        assert absent not in output


def test_old_list_positionals_are_rejected_with_gh_exit() -> None:
    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "list", "DEMO", "example-repo"],
    )
    assert result.exit_code == 1
    assert "unexpected extra arguments" in result.output.lower()


def test_json_missing_value_fails_before_context_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    result = runner.invoke(app, ["bitbucket", "pr", "list", "--json"])
    assert result.exit_code == 1
    assert "Specify one or more comma-separated fields" in result.stderr


def test_web_json_conflict_does_not_open_browser_or_resolve_repo(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "open_browser", lambda *_args, **_kwargs: pytest.fail("browser called"))
    monkeypatch.setattr(pr_module, "resolve_repository", lambda *_args, **_kwargs: pytest.fail("repo resolved"))
    result = runner.invoke(app, ["bitbucket", "pr", "list", "--json", "number", "--web"])
    assert result.exit_code == 1
    assert "cannot use `--web` with `--json`" in result.stderr


def test_view_repo_without_selector_fails_before_git_or_provider(monkeypatch) -> None:
    monkeypatch.setattr(pr_module, "GitRepositoryContext", lambda *_: pytest.fail("git called"))
    monkeypatch.setattr(pr_module, "build_provider", lambda *_: pytest.fail("provider called"))
    result = runner.invoke(
        app,
        ["bitbucket", "pr", "view", "-R", "DEMO/example-repo"],
    )
    assert result.exit_code == 1
    assert "argument required when using the --repo flag" in result.stderr


def test_hidden_ls_alias_invokes_primary_list(monkeypatch) -> None:
    install_read_fakes(monkeypatch)
    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "--username", "example-user", "--password", "example response", "bitbucket", "pr", "ls", "-R", "DEMO/example-repo", "--json", "number"],
    )
    assert result.exit_code == 0
    assert result.stdout == '[{"number":1234}]\n'


def test_hidden_legacy_output_selects_v019_renderer(monkeypatch) -> None:
    calls = install_legacy_list_fake(monkeypatch)
    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "--username", "example-user", "--password", "example response", "bitbucket", "pr", "list", "-R", "DEMO/example-repo", "--output", "json"],
    )
    assert result.exit_code == 0
    assert calls == [("DEMO", "example-repo", "OPEN", 0, 30)]
    assert '"results"' in result.stdout
```

Add tests that primary list maps `open/closed/merged/all`, forwards all supported filters, rejects limit zero, writes compact JSON, opens `--web` without listing, and uses the line presenter by default. Add view tests for numeric, URL, branch, and omitted-current-branch selection, `--comments`, JSON, `--web`, and PR URL authority over `-R`.

- [ ] **Step 2: Add failing browse preservation and compatibility visibility tests**

Move the existing interactive-list tests to `pr browse` and assert:

```python
def test_pr_browse_uses_existing_full_screen_browser_in_tty(monkeypatch) -> None:
    calls = install_browse_fakes(monkeypatch, interactive=True)
    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "browse", "DEMO", "example-repo", "--state", "OPEN", "--start", "0", "--limit", "25"],
    )
    assert result.exit_code == 0
    assert calls["source"].title == "Bitbucket pull requests"


@pytest.mark.parametrize("failure", [ImportError, RuntimeError])
def test_pr_browse_falls_back_to_static_markdown(failure, monkeypatch) -> None:
    install_browse_fakes(monkeypatch, browser_error=failure("example response"))
    result = runner.invoke(
        app,
        ["--url", "https://bitbucket.example.com", "bitbucket", "pr", "browse", "DEMO", "example-repo"],
    )
    assert result.exit_code == 0
    assert "Example pull request" in result.stdout
```

Assert `pr browse` is visible and documents only its two positionals plus `--state`, `--start`, and `--limit`. Assert `get`, `build-status`, `approve`, and `unapprove` remain callable but are hidden from `pr --help`; leave current `comment`, `diff`, `create`, and `merge` behavior unchanged in this phase.

- [ ] **Step 3: Introduce a typed missing-credential error without changing legacy exits**

Add this subclass to `core/errors.py`:

```python
class MissingCredentialError(ConfigError):
    """A command requires authentication but no credential was configured."""
```

In `auth/resolver.py`, raise it instead of generic `ConfigError` only for PAT/BEARER modes with no token. Existing `exit_code_for_error()` must not gain a special case, so compatibility commands still classify the subclass as the existing config exit. Extend `tests/auth/test_headers.py` to assert the concrete exception type while preserving the message.

Primary read commands also call this command-local check after static preflight and before provider construction:

```python
def require_primary_auth(auth: ResolvedAuth) -> None:
    has_authorization_header = any(
        name.lower() == "authorization" and bool(value)
        for name, value in auth.headers.items()
    )
    has_basic = bool(auth.username and (auth.password or auth.token))
    if not (auth.token or has_basic or has_authorization_header):
        raise MissingCredentialError("authentication required")
```

This preserves header-only authentication and avoids changing anonymous behavior for non-migrated commands.

- [ ] **Step 4: Implement a command-local Typer adapter for optional `--json` and parser exit `1`**

Typer normally rejects a bare value-taking option with exit `2`, before callbacks. Add one small `GhReadCommand(TyperCommand)` in `pr.py`; do not modify the root CLI or all Typer commands:

```python
def _normalize_json_argv(args: list[str]) -> list[str]:
    normalized: list[str] = []
    for index, value in enumerate(args):
        normalized.append(value)
        if value == "--json" and (
            index + 1 == len(args) or args[index + 1].startswith("-")
        ):
            normalized.append(MISSING_JSON_VALUE)
    return normalized


class GhReadCommand(TyperCommand):
    def parse_args(self, ctx, args):
        try:
            return super().parse_args(ctx, _normalize_json_argv(list(args)))
        except click.UsageError as exc:
            exc.exit_code = 1
            raise

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except click.UsageError as exc:
            exc.exit_code = 1
            raise
```

Register only primary `list`, hidden `ls`, and `view` with `cls=GhReadCommand`. Tests must cover bare `--json`, `--json --web`, `--json=number,title`, repeated `--json number --json title`, invalid state, too many view arguments, and old list positionals.

- [ ] **Step 5: Implement command-local GH error mapping**

Create `gh_compat/exit_policy.py`:

```python
def run_gh_read(action: Callable[[], None]) -> None:
    try:
        action()
    except (KeyboardInterrupt, click.Abort):
        raise typer.Exit(2) from None
    except GhPreflightError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    except RepositoryHostMismatchError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(4) from None
    except MissingCredentialError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(4) from None
    except click.BadParameter as exc:
        if isinstance(exc.__cause__, MissingCredentialError):
            typer.echo(f"Error: {exc.__cause__}", err=True)
            raise typer.Exit(4) from None
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
    except AtlassianCliError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
```

Do not catch `typer.Exit` success paths. Add tests proving migrated validation/not-found/network failures exit `1`, missing auth and foreign host exit `4`, and hidden compatibility commands still use the existing detailed exit policy.

- [ ] **Step 6: Rewire `pr list`, add `view`, and avoid unnecessary Git reads**

Move the current `list_pull_requests()` body unchanged into `browse_pull_requests(project_key, repo_slug, state="OPEN", start=0, limit=25)`. The fallback calls `payload = service.list(project_key, repo_slug, state, start=start, limit=limit)` and then `render_output(payload, output=OutputMode.MARKDOWN)`; `browse` has no structured `--output` option.

Implement primary list with this signature and defaults:

```python
@app.command("list", cls=GhReadCommand)
def list_pull_requests(
    ctx: typer.Context,
    author: str | None = typer.Option(None, "--author", "-A"),
    base: str | None = typer.Option(None, "--base", "-B"),
    head: str | None = typer.Option(None, "--head", "-H"),
    json_fields: list[str] = typer.Option([], "--json"),
    limit: int = typer.Option(30, "--limit", "-L"),
    repo: str | None = typer.Option(None, "--repo", "-R"),
    search: str | None = typer.Option(None, "--search", "-S"),
    state: str = typer.Option("open", "--state", "-s"),
    web: bool = typer.Option(False, "--web", "-w"),
    output: OutputMode | None = typer.Option(
        None,
        "--output",
        hidden=True,
        deprecated=True,
    ),
) -> None:
    run_gh_read(
        lambda: _list_run(
            ctx=ctx,
            author=author,
            base=base,
            head=head,
            json_fields=json_fields,
            limit=limit,
            repo=repo,
            search=search,
            state=state,
            web=web,
            output=output,
        )
    )
```

Define `_list_run()` with the same keyword-only parameters and concrete types shown in the callback; it returns `None` after exactly one of legacy output, web, JSON, or human presentation completes.

Register the same callback as hidden callable command `ls`. Validate repeated/comma-separated JSON, `--web` conflict, legacy `--output`/`--json` conflict, state enum, and positive limit before `ctx.obj` access. The D06 path requires `-R`/environment/Git resolution, maps state to the v0.1.19 uppercase state, calls the existing service, and renders its legacy envelope. The primary path uses `PullRequestReadService`; human mode requests only list presenter fields, while JSON requests exactly the validated fields. Pass `count_total=True` only for TTY human output and give `result.total_count` to `render_pr_list`; JSON/non-TTY use `count_total=False`. `--web` opens the Bitbucket repository PR-list URL with supported filters and does not call `list()`.

Because `--author`, `--base`, `--head`, `--search`, and `--web` never existed beside the legacy renderer, reject each when hidden `--output` is present instead of silently ignoring it. `--state`, `--limit`, and repository resolution remain valid on the D06 path. Add one unit case per rejected combination and assert zero provider calls.

The existing root-level `--output` appearing before `bitbucket` does not select D06 for primary commands; only the hidden option parsed after `pr list` does. Add a regression test showing root `--output json` still leaves primary list in GH human mode.

Implement `view [<number> | <url> | <branch>]` with `--comments/-c`, `--json`, `--repo/-R`, and `--web/-w`. Apply the `-R` omitted-selector guard before `ctx.obj`, Git, or provider access. Parse a valid PR URL before repository resolution and pass its embedded repository as highest precedence. Human view requests the fields its presenter needs; JSON requests only validated fields; web requests only `url` and emits no normal output.

After human or JSON rendering, send the complete string through `page_output`: list uses `error starting pager`, view uses `failed to start pager`. Non-TTY remains a direct write; TTY JSON therefore receives the same pager/color decision as the pinned exporter. Warnings stay on stderr and never contaminate compact JSON stdout.

For list/view web mode, write `Opening <display URL> in your browser.` to stderr only when stdout is a TTY, then call `open_browser(full_url)`. The display URL drops query/fragment while the browser receives the full URL. Assert the fixture's `browser_notice` and zero stdout; non-TTY opens silently.

Repository resolution reads Git only when no embedded URL repository, explicit `-R`, or `ATLASSIAN_BITBUCKET_REPO` is available. This keeps list/view-by-URL/view-by-number-with-`-R` usable outside a checkout and avoids a needless subprocess layer.

When Git resolution finds multiple matching remotes, pass `can_prompt(stdin.isatty, stdout.isatty, env)` and a command-local numbered chooser into `RepositoryResolver`. Render each remote name with its canonical `DEMO/example-repo`-style selector, require one valid choice, and let interrupt/cancel flow through `run_gh_read` as exit `2`. Non-TTY or `ATLASSIAN_PROMPT_DISABLED` continues to use the resolver's exact ambiguity error. Add one command test for each path and assert `GH_PROMPT_DISABLED` has no effect.

- [ ] **Step 7: Run focused command and compatibility tests**

```bash
.venv/bin/python -m pytest \
  tests/auth/test_headers.py \
  tests/products/bitbucket/test_pr_command.py \
  tests/test_cli_help.py -q
```

Expected: new grammar/output/exit tests pass and existing comment/diff/create/merge plus hidden compatibility command tests remain green.

- [ ] **Step 8: Commit command wiring**

```bash
git add \
  src/atlassian_cli/core/errors.py \
  src/atlassian_cli/auth/resolver.py \
  src/atlassian_cli/products/bitbucket/gh_compat/exit_policy.py \
  src/atlassian_cli/products/bitbucket/commands/pr.py \
  tests/auth/test_headers.py \
  tests/products/bitbucket/test_pr_command.py \
  tests/test_cli_help.py
git commit -m "feat: add gh-compatible pull request read commands"
```

---

### Task 8: README, Live E2E, and Repository Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/e2e/support/runner.py`
- Modify: `tests/e2e/coverage_manifest.py`
- Modify: `tests/e2e/test_bitbucket_live.py`
- Modify: `tests/test_readme.py`

**Interfaces:**
- Consumes: completed public command surface and the configured Bitbucket Server 6.7.2 live environment.
- Produces: public migration documentation, manifest coverage for every new leaf/alias, feature-specific live evidence, and full repository gate evidence.

- [ ] **Step 1: Write failing README assertions**

Extend `tests/test_readme.py` with exact public examples and migration notes:

```python
def test_readme_documents_gh_compatible_pr_reads_and_browser_migration() -> None:
    readme = Path("README.md").read_text()
    assert "atlassian bitbucket pr list -R DEMO/example-repo" in readme
    assert "atlassian bitbucket pr view 1234 -R DEMO/example-repo" in readme
    assert "atlassian bitbucket pr browse DEMO example-repo" in readme
    assert "`pr list` is line-oriented" in readme
    assert "`pr browse` preserves the full-screen browser" in readme
    assert "Bitbucket Server 6.7.2" in readme
    assert "B25" in readme
    assert "B30" in readme
    assert "B31" in readme


def test_readme_no_longer_leads_with_removed_pr_list_positionals() -> None:
    readme = Path("README.md").read_text()
    assert "atlassian bitbucket pr list DEMO example-repo" not in readme
```

- [ ] **Step 2: Rewrite the PR read examples and compatibility section**

Update all old list examples to the new grammar and add these primary forms:

```text
atlassian bitbucket pr list -R DEMO/example-repo
atlassian bitbucket pr list -R DEMO/example-repo --state merged --limit 30
atlassian bitbucket pr list -R DEMO/example-repo --json number,title,state,url
atlassian bitbucket pr view 1234 -R DEMO/example-repo
atlassian bitbucket pr view feature/DEMO-1234/example-change -R DEMO/example-repo
atlassian bitbucket pr browse DEMO example-repo
```

Document that `list` defaults to open/30, `closed` maps to declined PRs, `--web` conflicts with `--json`, `ATLASSIAN_BITBUCKET_REPO` supplies repository context, and base JSON is available without `--jq`/`--template` in this phase. State that `reviews`/`latestReviews` (B30), `mergeCommit` (B31), and `potentialMergeCommit` (B25) are parser-visible capability failures on Bitbucket Server 6.7.2.

Add one compact migration table: old `pr list PROJECT REPO` becomes `pr list -R PROJECT/REPO`; the old full-screen list becomes `pr browse PROJECT REPO`; existing list `--output` remains hidden/deprecated; `get`, `build-status`, `approve`, and `unapprove` remain callable; migrated primary reads use exits `0/1/2/4`. Remove claims that all collection commands open the interactive browser because primary `pr list` no longer does.

- [ ] **Step 3: Extend the e2e runner for current-checkout selection**

Change runner signatures without affecting existing callers:

```python
def run_cli(
    live_env: LiveEnv,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _load_dotenv_values()
    env.update(os.environ)
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{SRC_ROOT}{os.pathsep}{pythonpath}" if pythonpath else str(SRC_ROOT)
    )
    command = [
        sys.executable,
        "-m",
        "atlassian_cli.main",
        "--config-file",
        str(live_env.config_file),
        *args,
    ]
    return subprocess.run(
        command,
        cwd=cwd or REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def run_json(live_env: LiveEnv, *args: str, cwd: Path | None = None):
    result = run_cli(live_env, *args, cwd=cwd)
    if result.returncode != 0:
        raise AssertionError(
            "CLI command failed\n"
            f"command: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout)
```

Add a runner unit test if one exists; otherwise the live current-branch assertion below exercises the new argument.

- [ ] **Step 4: Update manifest entries and the existing PR round trip**

Map all new leaves/aliases to the existing feature live test:

```python
"bitbucket pr list": "test_bitbucket_branch_and_pr_round_trip_live",
"bitbucket pr ls": "test_bitbucket_branch_and_pr_round_trip_live",
"bitbucket pr view": "test_bitbucket_branch_and_pr_round_trip_live",
"bitbucket pr browse": "test_bitbucket_branch_and_pr_round_trip_live",
```

Before the existing merge step in `test_bitbucket_branch_and_pr_round_trip_live`, replace the old positional list invocation and add:

```python
repo_selector = f"{target['project_key']}/{target['repo_slug']}"

listed = run_json(
    live_env,
    "bitbucket", "pr", "list",
    "-R", repo_selector,
    "--head", branch_name,
    "--json", "number,title,state,url",
)
assert any(item["number"] == pr_id for item in listed)

listed_via_alias = run_json(
    live_env,
    "bitbucket", "pr", "ls",
    "-R", repo_selector,
    "--json", "number",
)
assert any(item["number"] == pr_id for item in listed_via_alias)

viewed = run_json(
    live_env,
    "bitbucket", "pr", "view", str(pr_id),
    "-R", repo_selector,
    "--json", "number,title,state,url,headRefName",
)
assert viewed["number"] == pr_id
assert viewed["headRefName"] == branch_name

viewed_from_branch = run_json(
    live_env,
    "bitbucket", "pr", "view",
    "--json", "number",
    cwd=sandbox_path,
)
assert viewed_from_branch["number"] == pr_id

pr_url = viewed["url"]
viewed_from_url = run_json(
    live_env,
    "bitbucket", "pr", "view", pr_url,
    "-R", "~example-user/example-repo",
    "--json", "number,url",
)
assert viewed_from_url == {"number": pr_id, "url": pr_url}

browsed = run_cli(
    live_env,
    "bitbucket", "pr", "browse",
    target["project_key"], target["repo_slug"],
    "--state", "OPEN", "--limit", "1",
)
assert browsed.returncode == 0
assert "Example pull request" in browsed.stdout
```

Keep all existing cleanup registration before mutations. Use the approved fixed title `Example pull request`; do not add internal-looking project/repository/branch/title values. The PR URL test intentionally supplies a different approved `-R` selector to prove URL authority without accessing that repository.

Because this task touches the existing public live-test file, normalize its nearby resource literals in the same edit: `unique_name("atlassian-cli-e2e-repo") -> unique_name("example-repo")`, `unique_name("e2e-branch") -> unique_name("feature/DEMO-1234/example-change")`, `unique_name("e2e-pr") -> unique_name("Example pull request")`, `created by live e2e -> example response`, and `e2e-note.txt -> example.py`. Keep functional standard names such as `README.md` and the target repository's existing default branch unchanged. Import `run_cli` alongside `run_json` for the browse assertion.

- [ ] **Step 5: Run unit/docs/manifest tests**

```bash
.venv/bin/python -m pytest \
  tests/test_readme.py \
  tests/e2e/test_coverage_manifest.py \
  tests/products/bitbucket/test_pr_command.py -q
```

Expected: README assertions, command tests, and coverage-manifest completeness pass.

- [ ] **Step 6: Run the required Bitbucket Server 6.7.2 live path**

```bash
ATLASSIAN_E2E=1 .venv/bin/python -m pytest \
  tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live -q
```

Expected: PASS against the configured Atlassian Bitbucket Server 6.7.2 instance, covering primary list/alias/view/current-branch/URL/browse plus existing compatibility flows. If the live environment is unavailable, stop and report this explicit blocker; do not call the feature live-verified.

- [ ] **Step 7: Run public-sample and plan placeholder scans**

```bash
rg -n -i 'a[g]ora|a[g]oralab|NMS-[0-9]+|PROJ-[0-9]+' \
  README.md \
  docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-design.md \
  docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-matrix.md \
  docs/superpowers/plans/2026-07-16-atlassian-cli-gh-bitbucket-pr-read-workflows.md \
  tests/fixtures/gh-v2.96.0 \
  tests/products/bitbucket/test_gh_*.py \
  tests/products/bitbucket/test_pr_read_service.py \
  tests/e2e/test_bitbucket_live.py
rg -n 'T[B]D|T[O]DO|implement l[a]ter|fill in d[e]tails|appropriate error h[a]ndling|similar to T[a]sk' \
  docs/superpowers/plans/2026-07-16-atlassian-cli-gh-bitbucket-pr-read-workflows.md
```

Expected: both commands return no matches. Review every new/changed sample manually against the approved neutral placeholder set, including PR URLs and branch selectors.

- [ ] **Step 8: Run full repository quality gates**

```bash
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: every command exits `0`.

- [ ] **Step 9: Commit docs and live coverage**

```bash
git add \
  README.md \
  tests/e2e/support/runner.py \
  tests/e2e/coverage_manifest.py \
  tests/e2e/test_bitbucket_live.py \
  tests/test_readme.py
git commit -m "docs: document gh-compatible pull request reads"
```

- [ ] **Step 10: Final spec-to-plan review**

Before handing off, verify each first-slice matrix row has one owner:

```text
selection precedence and D01       -> Tasks 2, 3, 4, 6
list/ls grammar and defaults       -> Tasks 1, 5, 7
view grammar and -R guard          -> Tasks 1, 4, 7
base JSON and B25/B30/B31          -> Tasks 1, 5, 6
D06 hidden legacy output           -> Task 7
pr browse preservation/fallback    -> Task 7
GH exits on migrated commands only -> Task 7
README/manifest/live 6.7.2         -> Task 8
```

Recheck that later tasks use the exact signatures defined earlier, all production code paths are read-only, and no step introduces a generic Git/provider/output framework. Inspect `git status --short` and preserve unrelated user changes.

---

## Execution Notes

- Execute in a dedicated worktree; use the shared repository `.venv` if that worktree has none.
- Each task ends in an independently reviewable Conventional Commit. Do not squash tasks during implementation unless requested.
- The live e2e result is mandatory evidence for completion, not an optional postscript.
