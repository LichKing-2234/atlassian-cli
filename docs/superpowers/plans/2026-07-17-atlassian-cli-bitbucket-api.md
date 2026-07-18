# Bitbucket API Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic `atlassian bitbucket api` REST command whose applicable flags and observable behavior match `gh api v2.96.0`, with Bitbucket Server 6.7.2 compare diff, changes, and commits as the initial live-verified capability.

**Architecture:** Keep field parsing, authenticated HTTP transport, and terminal rendering independent. A pure field parser reproduces gh nested and typed parameter semantics; a Bitbucket API service resolves server-relative endpoints and standard pagination through one provider raw-request primitive; the Typer command owns gh-compatible validation, output, jq, redaction, and exits.

**Tech Stack:** Python 3.12 source, Python 3.10 PyOxidizer runtime, Typer/Click, requests through `atlassian-python-api`, Python `jq` binding, pytest, Ruff.

## Global Constraints

- Baseline is `gh v2.96.0` at commit `b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0`.
- Target is Atlassian Bitbucket Server `6.7.2`; Bitbucket Cloud remains unsupported.
- The command is generic REST transport; compare endpoints are acceptance coverage, not an allowlist.
- Do not implement GraphQL, `--template`, `--cache`, `--preview`, or command-local `--hostname`.
- Do not add `--output`, normalized compare schemas, a `bitbucket compare` group, or unified-diff synthesis.
- The standalone Linux amd64 bundle must not require a GLIBC version newer than 2.28.
- Use only the repository-approved neutral placeholder set in code, tests, docs, fixtures, commits, and PR metadata.
- Follow TDD: add each behavioral test first, observe the expected failure, then add the minimum implementation.
- Any new command must update `tests/e2e/coverage_manifest.py` and its live e2e path.
- Use the repository virtual environment.

---

### Task 1: Parse gh-Compatible API Fields

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/api_fields.py`
- Create: `tests/products/bitbucket/test_api_fields.py`

**Interfaces:**
- Produces: `fill_placeholders(value: str, resolver: Callable[[str], str]) -> str`
- Produces: `parse_api_fields(raw_fields: Sequence[str], typed_fields: Sequence[str], *, resolver: Callable[[str], str], stdin: TextIO) -> dict[str, object]`
- Consumes: a resolver whose argument is one of `project`, `repo`, or `branch`
- Guarantees: raw fields are applied before typed fields regardless of CLI ordering, matching pinned gh source

- [ ] **Step 1: Write failing scalar and placeholder tests**

Create `tests/products/bitbucket/test_api_fields.py` with focused tests like:

```python
from io import StringIO

import pytest

from atlassian_cli.products.bitbucket.api_fields import parse_api_fields


def resolve(name: str) -> str:
    return {
        "project": "DEMO",
        "repo": "example-repo",
        "branch": "feature/DEMO-1234/example-change",
    }[name]


def test_parse_api_fields_keeps_raw_values_and_converts_typed_values() -> None:
    result = parse_api_fields(
        ["raw=true"],
        ["count=42", "enabled=true", "missing=null", "repo={repo}"],
        resolver=resolve,
        stdin=StringIO(""),
    )

    assert result == {
        "raw": "true",
        "count": 42,
        "enabled": True,
        "missing": None,
        "repo": "example-repo",
    }


def test_parse_api_fields_rejects_unknown_placeholder() -> None:
    with pytest.raises(ValueError, match="unknown placeholder"):
        parse_api_fields([], ["value={owner}"], resolver=resolve, stdin=StringIO(""))
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```sh
.venv/bin/python -m pytest -q tests/products/bitbucket/test_api_fields.py
```

Expected: collection fails because `api_fields.py` does not exist.

- [ ] **Step 3: Add the minimal scalar parser**

Create `api_fields.py` with these implementation units:

```python
PLACEHOLDER_PATTERN = re.compile(r"\{([a-z]+)\}")


def fill_placeholders(value: str, resolver: Callable[[str], str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in {"project", "repo", "branch"}:
            raise ValueError(f"unknown placeholder: {name}")
        return resolver(name)

    return PLACEHOLDER_PATTERN.sub(replace, value)


def _typed_value(value: str, *, resolver, stdin):
    if value.startswith("@"):
        source = value[1:]
        return stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    try:
        return int(value)
    except ValueError:
        pass
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    return fill_placeholders(value, resolver)
```

Implement top-level `key=value` parsing first, with raw fields processed before typed fields and duplicate scalar keys rejected.

- [ ] **Step 4: Verify scalar tests GREEN**

Run the focused test file. Expected: scalar and placeholder tests pass.

- [ ] **Step 5: Add failing nested, array, file, stdin, and conflict tests**

Cover all pinned gh forms:

```python
def test_parse_api_fields_builds_nested_objects_and_arrays() -> None:
    result = parse_api_fields(
        [],
        [
            "properties[][property_name]=DEMO",
            "properties[][allowed_values][]=DEMO-1",
            "properties[][allowed_values][]=DEMO-1234",
            "empty[]=",
        ],
        resolver=resolve,
        stdin=StringIO(""),
    )

    assert result == {
        "properties": [
            {
                "property_name": "DEMO",
                "allowed_values": ["DEMO-1", "DEMO-1234"],
            }
        ],
        "empty": [""],
    }


def test_parse_api_fields_accepts_empty_array_declaration() -> None:
    assert parse_api_fields(
        ["reviewers[]"], [], resolver=resolve, stdin=StringIO("")
    ) == {"reviewers": []}
```

Also test `@file`, `@-`, missing equals, empty key, scalar/object collision,
scalar/array collision, and raw-before-typed duplicate detection.

- [ ] **Step 6: Run nested tests and verify RED**

Expected: nested and array assertions fail while existing scalar tests remain green.

- [ ] **Step 7: Implement pinned gh nesting behavior**

Port the small `parseFields`, `addParamsMap`, and `addParamsSlice` algorithm from
the pinned gh source into idiomatic Python. Do not introduce a general query
language or schema layer. Preserve these exact rules:

```text
key[subkey]=value       -> nested object
key[]=value             -> append scalar array value
key[]                   -> empty array
items[][name]=value     -> append or reuse the last object when compatible
```

- [ ] **Step 8: Run Task 1 tests and formatting**

```sh
.venv/bin/python -m pytest -q tests/products/bitbucket/test_api_fields.py
.venv/bin/ruff format --check src/atlassian_cli/products/bitbucket/api_fields.py tests/products/bitbucket/test_api_fields.py
.venv/bin/ruff check src/atlassian_cli/products/bitbucket/api_fields.py tests/products/bitbucket/test_api_fields.py
```

Expected: all pass.

- [ ] **Step 9: Commit Task 1**

```sh
git add src/atlassian_cli/products/bitbucket/api_fields.py tests/products/bitbucket/test_api_fields.py
git commit -m "feat: parse GitHub-compatible API fields"
```

---

### Task 2: Add Authenticated REST Transport And Bitbucket Pagination

**Files:**
- Modify: `src/atlassian_cli/products/bitbucket/providers/base.py`
- Modify: `src/atlassian_cli/products/bitbucket/providers/server.py`
- Create: `src/atlassian_cli/products/bitbucket/services/api.py`
- Modify: `tests/products/bitbucket/test_provider.py`
- Create: `tests/products/bitbucket/test_api_service.py`

**Interfaces:**
- Produces provider method:

```python
def request_api(
    self,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None,
    params: dict[str, object] | None,
    json_body: dict[str, object] | None,
    data: bytes | None,
): ...
```

- Produces `normalize_api_endpoint(endpoint: str) -> str`
- Produces immutable `ApiRequest` with `endpoint`, `method`, `headers`, `fields`, and `input_body`
- Produces `BitbucketApiService.iter_responses(request: ApiRequest, *, paginate: bool) -> Iterator[object]`

- [ ] **Step 1: Write the failing provider primitive test**

Add a provider test that asserts exact forwarding:

```python
def test_bitbucket_provider_request_api_returns_advanced_response() -> None:
    calls = {}
    response = object()

    class FakeClient:
        def request(self, **kwargs):
            calls.update(kwargs)
            return response

    provider = build_provider_with_client(FakeClient())
    result = provider.request_api(
        "GET",
        "rest/api/1.0/projects/DEMO/repos/example-repo/compare/changes",
        headers={"Accept": "application/json"},
        params={"from": "feature/DEMO-1234/example-change", "to": "DEMO"},
        json_body=None,
        data=None,
    )

    assert result is response
    assert calls["advanced_mode"] is True
```

- [ ] **Step 2: Run the provider test and verify RED**

Expected: `BitbucketServerProvider` has no `request_api` method.

- [ ] **Step 3: Add the provider protocol and implementation**

Add the exact signature to `BitbucketProvider`. In the Server provider, delegate
to `self.client.request(method=..., path=..., headers=..., params=...,
json=json_body, data=data, advanced_mode=True)`. Do not call
`raise_for_status`; raw HTTP status and body belong to the API command.

- [ ] **Step 4: Verify the provider test GREEN**

Run only the new provider test. Expected: pass.

- [ ] **Step 5: Write failing endpoint and method/body service tests**

Create `test_api_service.py` with a minimal fake response and fake provider.
Assert:

```python
assert normalize_api_endpoint(
    "projects/DEMO/repos/example-repo/compare/diff"
) == "rest/api/1.0/projects/DEMO/repos/example-repo/compare/diff"
assert normalize_api_endpoint(
    "/rest/build-status/1.0/commits/DEMO"
) == "rest/build-status/1.0/commits/DEMO"
```

Assert absolute `https://bitbucket.example.com/...` endpoints and `graphql`
raise `ValueError` before the provider is called. Assert GET fields become
`params`, POST fields become `json_body`, and `input_body` makes fields query
parameters for any method.

- [ ] **Step 6: Run service request tests and verify RED**

Expected: module or service interfaces are missing.

- [ ] **Step 7: Implement endpoint and one-request behavior**

Create:

```python
@dataclass(frozen=True)
class ApiRequest:
    endpoint: str
    method: str
    headers: dict[str, str]
    fields: dict[str, object]
    input_body: bytes | None = None


class BitbucketApiService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def iter_responses(self, request: ApiRequest, *, paginate: bool):
        ...
```

`normalize_api_endpoint` strips one leading slash, rejects schemes/netlocs,
uses `rest/...` unchanged, and prefixes every other relative endpoint with
`rest/api/1.0/`. Preserve an existing query string via `urllib.parse` rather
than string concatenation.

- [ ] **Step 8: Verify one-request tests GREEN**

Run the service test file. Expected: endpoint and method/body tests pass.

- [ ] **Step 9: Write failing pagination tests**

Use three fake page responses and assert:

- `limit=100` is added only when absent;
- `start` follows `nextPageStart` without losing compare fields;
- `isLastPage: true` stops;
- missing page metadata and non-JSON bodies stop after one response;
- missing, repeated, or decreasing `nextPageStart` raises `ValueError`;
- non-GET pagination is rejected before the first provider call.

Use payloads shaped like:

```python
{
    "size": 1,
    "limit": 100,
    "isLastPage": False,
    "nextPageStart": 100,
    "values": [{"id": "DEMO"}],
    "start": 0,
}
```

- [ ] **Step 10: Run pagination tests and verify RED**

Expected: only the first response is returned or paging guards are absent.

- [ ] **Step 11: Implement standard Bitbucket paging**

Parse JSON only for paging metadata. Yield each raw response before deciding
whether to continue. Maintain a set of seen starts and reject non-increasing
values. Never normalize or merge page bodies in the service.

- [ ] **Step 12: Run Task 2 tests and formatting**

```sh
.venv/bin/python -m pytest -q tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_api_service.py
.venv/bin/ruff format --check src/atlassian_cli/products/bitbucket/providers src/atlassian_cli/products/bitbucket/services/api.py tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_api_service.py
.venv/bin/ruff check src/atlassian_cli/products/bitbucket/providers src/atlassian_cli/products/bitbucket/services/api.py tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_api_service.py
```

Expected: all pass.

- [ ] **Step 13: Commit Task 2**

```sh
git add src/atlassian_cli/products/bitbucket/providers/base.py src/atlassian_cli/products/bitbucket/providers/server.py src/atlassian_cli/products/bitbucket/services/api.py tests/products/bitbucket/test_provider.py tests/products/bitbucket/test_api_service.py
git commit -m "feat: add Bitbucket API transport"
```

---

### Task 3: Expose The gh-Compatible API Command And Output Pipeline

**Files:**
- Create: `src/atlassian_cli/products/bitbucket/commands/api.py`
- Modify: `src/atlassian_cli/cli.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/products/bitbucket/test_api_command.py`
- Modify: `tests/test_cli_help.py`

**Interfaces:**
- Produces `api_command` registered as `atlassian bitbucket api`
- Consumes `parse_api_fields`, `ApiRequest`, and `BitbucketApiService.iter_responses`
- Supported flags: `-F`, `-H`, `-i`, `--input`, `-q`, `-X`, `--paginate`, `-f`, `--silent`, `--slurp`, `--verbose`
- Produces gh-compatible usage/HTTP exits: validation and HTTP/network `1`, auth `4`, cancellation `2`

- [ ] **Step 1: Write failing command help and registration tests**

Add a help test that asserts the endpoint metavar and every supported flag are
visible, while `--output`, `--template`, `--cache`, `--preview`, and
`--hostname` are absent. Add a command test that invokes:

```python
result = runner.invoke(
    app,
    [
        "--url",
        "https://bitbucket.example.com",
        "--auth",
        "pat",
        "--token",
        "example response",
        "bitbucket",
        "api",
        "projects/DEMO/repos/example-repo/compare/changes",
    ],
)
```

Mock `build_provider` and assert the service receives a GET `ApiRequest`.

- [ ] **Step 2: Run registration tests and verify RED**

Expected: `No such command 'api'`.

- [ ] **Step 3: Add the command skeleton and registration**

Create `api.py` with a Typer callback using the exact flags and aliases. Add a
small `GhApiCommand(TyperCommand)` that maps Typer/Click parsing errors to exit
`1`, as the existing migrated PR commands do. Register `api_command` directly
on `bitbucket_app` in `cli.py`; this is a command, not a nested Typer group.

Perform static validation before resolving lazy config or building the provider.
Use `ctx.get_parameter_source("method")` to distinguish the default GET from an
explicit `-X GET`. Derive POST when fields or input are present and method was
not explicit.

- [ ] **Step 4: Verify registration tests GREEN**

Run the new command tests and `tests/test_cli_help.py`. Expected: registration
and help pass; output behavior remains pending.

- [ ] **Step 5: Write failing request-construction and validation tests**

Cover:

- default GET and derived POST;
- explicit `-X GET -f from=... -f to=...`;
- `--input` body plus query fields and `@-` stdin;
- command-line header parsing and case-insensitive override;
- absolute URL and GraphQL rejection before provider construction;
- paginate/non-GET, paginate/input, slurp-without-paginate,
  slurp/jq, and jq/silent/verbose conflicts;
- missing authentication exit `4`;
- usage and unexpected argument exit `1`.

- [ ] **Step 6: Run the new tests and verify RED**

Expected: validation or construction behavior is missing.

- [ ] **Step 7: Implement request construction and gh exits**

Reuse the existing Bitbucket repository resolver only when `{project}`,
`{repo}`, or `{branch}` occurs in the endpoint or a typed field. Resolve all
placeholders once, then parse fields. Read `--input -` as bytes from stdin and
regular files with `Path.read_bytes()`.

Require primary authentication using the same predicate as `bitbucket pr`:
token, Basic credentials, or a non-empty Authorization header. Keep one shared
helper rather than two diverging copies.

- [ ] **Step 8: Add jq dependency and failing jq/output tests**

Add `jq>=1.10.0` to runtime dependencies and refresh `uv.lock`:

```sh
uv lock
uv pip install --python .venv/bin/python -e '.[dev]'
```

Write tests with fake responses for:

- raw JSON and text bodies;
- `204` no-content;
- jq string, object, boolean, null, and multiple results;
- jq syntax failure exit `1`;
- jq per paginated page;
- `--slurp` outer array;
- `--include` status and sorted headers;
- `--silent` body suppression;
- TTY pager and non-TTY direct output;
- `--verbose` request/response output with Authorization, cookie, configured
  header values, and token values absent;
- HTTP error body preserved, Bitbucket `errors[].message` summarized on stderr,
  and exit `1`;
- error JSON bypasses jq.

- [ ] **Step 9: Run output tests and verify RED**

Expected: response output helpers and jq behavior are missing.

- [ ] **Step 10: Implement raw, jq, include, silent, verbose, and error output**

Use the Python `jq` binding directly:

```python
results = jq.compile(expression).input_value(payload).all()
```

Format jq results like gh: strings unquoted, objects and arrays compact JSON,
booleans lowercase, null as a blank line, and one newline per result. Run jq
per response page. For `--slurp`, decode every successful JSON page and emit a
single outer array.

For HTTP status `>=300`, write the raw body even when jq was requested, then
write `atlassian: <message> (HTTP <status>)` to stderr and exit `1`. Do not pass
raw HTTP failures through the repository's normalized error mapper.

Render verbose output from the prepared request and response. Redact secret
header names case-insensitively and replace every non-empty known credential or
configured header value before writing. Never log secrets through exceptions.

- [ ] **Step 11: Run Task 3 focused and regression tests**

```sh
.venv/bin/python -m pytest -q tests/products/bitbucket/test_api_command.py tests/test_cli_help.py tests/products/bitbucket/test_pr_command.py
.venv/bin/ruff format --check pyproject.toml src/atlassian_cli/cli.py src/atlassian_cli/products/bitbucket/commands/api.py tests/products/bitbucket/test_api_command.py tests/test_cli_help.py
.venv/bin/ruff check pyproject.toml src/atlassian_cli/cli.py src/atlassian_cli/products/bitbucket/commands/api.py tests/products/bitbucket/test_api_command.py tests/test_cli_help.py
```

Expected: all pass.

- [ ] **Step 12: Build and smoke-test the local PyOxidizer bundle**

```sh
.venv/bin/python .github/scripts/build-pyoxidizer-artifact.py --target-os darwin --target-arch arm64 --version 0.1.19 --archive-format tar.gz
dist/atlassian/atlassian bitbucket api --help
```

Expected: the bundle builds, `--help` lists the supported API flags, and Python
3.10 imports the jq native extension successfully.

- [ ] **Step 13: Commit Task 3**

```sh
git add pyproject.toml uv.lock src/atlassian_cli/cli.py src/atlassian_cli/products/bitbucket/commands/api.py tests/products/bitbucket/test_api_command.py tests/test_cli_help.py
git commit -m "feat: add GitHub-compatible Bitbucket API command"
```

---

### Task 4: Document And Live-Verify Compare API Capability

**Files:**
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Modify: `tests/e2e/coverage_manifest.py`
- Modify: `tests/e2e/test_bitbucket_live.py`

**Interfaces:**
- Documents the generic command and the three compare endpoint invocations
- Maps `bitbucket api` to `test_bitbucket_branch_and_pr_round_trip_live`
- Uses the existing live temporary branch and commit as known compare refs

- [ ] **Step 1: Write failing README and coverage-manifest tests**

Add assertions that README contains:

```text
atlassian bitbucket api -X GET
projects/DEMO/repos/example-repo/compare/diff
projects/DEMO/repos/example-repo/compare/changes
projects/DEMO/repos/example-repo/compare/commits
```

Add `"bitbucket api": "test_bitbucket_branch_and_pr_round_trip_live"` to the
manifest only after its manifest test fails.

- [ ] **Step 2: Run documentation/manifest tests and verify RED**

```sh
.venv/bin/python -m pytest -q tests/test_readme.py tests/e2e/test_coverage_manifest.py
```

Expected: README and manifest assertions fail.

- [ ] **Step 3: Add concise API documentation and manifest entry**

Document that endpoint paths are relative to `rest/api/1.0` unless they start
with `rest/`, and that `-f/-F` derive POST unless users specify `-X GET`.
Document compare examples with only `DEMO`, `example-repo`,
`feature/DEMO-1234/example-change`, and the other approved neutral values. State
that Bitbucket Server 6.7.2 `compare/diff` returns structured JSON.

- [ ] **Step 4: Verify documentation/manifest tests GREEN**

Run the focused tests. Expected: pass.

- [ ] **Step 5: Add compare calls to the existing live round trip**

After the temporary branch is pushed and before cleanup, invoke:

```text
bitbucket api -X GET projects/<project>/repos/<repo>/compare/diff
bitbucket api -X GET --paginate --jq '.values[].path.toString' .../compare/changes
bitbucket api -X GET --paginate --jq '.values[].id' .../compare/commits
```

Pass the generated branch as `from` and the seeded target ref as `to`. Assert
the diff contains `diffs`, changes include `README.md` or the existing neutral
test path created by the round trip, and commits include the sandbox HEAD SHA.
Do not add fixed internal refs, project names, or repository names to the test.

- [ ] **Step 6: Run the live e2e and verify GREEN**

```sh
ATLASSIAN_E2E=1 .venv/bin/python -m pytest -q tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live
```

Expected: pass against the direct reachable Bitbucket Server 6.7.2 host. If the
configured `-api` host returns its known IP-restriction response, use the same
temporary direct-host override established for the current change and do not persist any
credential or private hostname in the repository.

- [ ] **Step 7: Run the public-data scan**

```sh
git diff origin/main --unified=0 -- README.md tests | \
  rg '^\+[^+].*(release/[0-9]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})'
```

Expected: no newly added internal or production-like sample data. Manually
review the added lines in this spec and plan against the same rule because a
scan command embedded in the plan can match its own patterns.

- [ ] **Step 8: Commit Task 4**

```sh
git add README.md tests/test_readme.py tests/e2e/coverage_manifest.py tests/e2e/test_bitbucket_live.py
git commit -m "docs: document Bitbucket compare API usage"
```

---

### Task 5: Complete Repository, Binary, CI, And PR Verification

**Files:**
- Modify only if verification exposes a scoped defect
- Update the current pull request metadata after all local and live checks pass

**Interfaces:**
- Final source suite and lint gates
- Final standalone binary at `~/.local/bin`
- The current pull request includes the generic compare API capability and remains ready for review

- [ ] **Step 1: Run focused API tests together**

```sh
.venv/bin/python -m pytest -q \
  tests/products/bitbucket/test_api_fields.py \
  tests/products/bitbucket/test_api_service.py \
  tests/products/bitbucket/test_api_command.py \
  tests/products/bitbucket/test_provider.py \
  tests/test_cli_help.py \
  tests/test_readme.py \
  tests/e2e/test_coverage_manifest.py
```

Expected: all pass.

- [ ] **Step 2: Run repository quality gates**

```sh
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/ruff check README.md pyproject.toml src tests docs
```

Expected: all pass with the existing intentional skips only.

- [ ] **Step 3: Re-run the affected live e2e from final HEAD**

```sh
ATLASSIAN_E2E=1 .venv/bin/python -m pytest -q tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live
```

Expected: pass. A live-environment failure is a blocker and must be reported as
such rather than called live-verified.

- [ ] **Step 4: Rebuild and install final macOS arm64 binary**

Build from final HEAD, smoke `bitbucket api --help`, exercise a compare GET, and
replace the existing local bundle only after the smoke checks pass. Preserve a
timestamped backup under `~/.local/bin/.atlassian-cli`.

- [ ] **Step 5: Inspect final diff and public samples**

```sh
git diff origin/main...HEAD --check
git status --short --branch
git log --oneline origin/main..HEAD
```

Review command grammar, output, error paths, dependency/build changes, README,
e2e manifest, and public placeholder compliance. Do not rewrite unrelated user
changes.

- [ ] **Step 6: Push and wait for GitHub verification**

```sh
git push origin HEAD
gh pr checks --watch
```

Expected: the verify check passes.
The verify job includes the pinned manylinux 2.28 PyOxidizer smoke build and its
GLIBC symbol check; this must remain green after adding jq.

- [ ] **Step 7: Update the current pull request title/body without private data**

Keep the Conventional Commit PR title. Update the body to state that the change
provides gh-compatible pull request reads and compare capability through the
generic `atlassian bitbucket api` command. Include local suite, live e2e, standalone
binary, and CI results using only public-safe identifiers.

- [ ] **Step 8: Verify final remote state**

```sh
gh pr view --json isDraft,mergeStateStatus,headRefOid,statusCheckRollup,url
git status --short --branch
```

Expected: PR is not draft, merge state is clean, checks pass, remote head equals
local HEAD, and the worktree is clean.
