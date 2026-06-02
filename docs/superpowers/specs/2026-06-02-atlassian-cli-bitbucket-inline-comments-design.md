# Atlassian CLI Bitbucket Inline Comments Design

## Context

Bitbucket pull request comments and pull request diff commands already exist.
The current `bitbucket pr comment add` command creates top-level pull request
comments only, while `bitbucket pr comment reply` handles comment replies.
Existing comment output already normalizes an `anchor` field when Bitbucket
returns one, so inline comments can be listed and read, but they cannot yet be
created from the CLI.

The current `bitbucket pr diff` command fetches the text `.diff` endpoint. That
is useful for human review and patch-style output, but line coordinates are only
available indirectly through unified diff hunk headers. Inline comment creation
needs explicit Bitbucket anchor coordinates, so this phase adds a structured
line-aware diff mode and uses those coordinates to create inline comments.

This design follows the approved direction:

- keep `bitbucket pr diff` backward compatible by default;
- add a line-aware option to the existing diff command;
- add optional inline anchor parameters to `bitbucket pr comment add`.

## Goals

- Support structured pull request diff output with per-line old and new line
  coordinates.
- Generate a stable `anchor` object for lines that can be used by
  `bitbucket pr comment add`.
- Support inline pull request comment creation through `--path`, `--line`, and
  `--line-type`.
- Preserve existing top-level pull request comment behavior when inline options
  are omitted.
- Keep raw output available for Bitbucket API troubleshooting.
- Update unit tests, README examples, and live e2e coverage for the new behavior.

## Non-Goals

- Do not replace the default human-readable text diff output.
- Do not add a new `bitbucket pr diff-lines` command in this phase.
- Do not add an interactive inline-comment picker.
- Do not infer or repair invalid anchors after Bitbucket rejects them.
- Do not add Bitbucket Cloud support; v1 remains Server/Data Center only.
- Do not change `reply`, `edit`, or `delete` semantics for pull request
  comments.

## Command Surface

Existing text diff behavior remains unchanged:

```bash
atlassian bitbucket pr diff DEMO example-repo 42
```

Line-aware diff output is selected with `--with-lines`:

```bash
atlassian bitbucket pr diff DEMO example-repo 42 --with-lines --output json
```

Inline comment creation extends the existing comment add command:

```bash
atlassian bitbucket pr comment add DEMO example-repo 42 "example comment" \
  --path example.py \
  --line 12 \
  --line-type ADDED
```

Without inline options, `comment add` keeps creating a top-level pull request
comment:

```bash
atlassian bitbucket pr comment add DEMO example-repo 42 "example comment"
```

If any inline option is present, all three inline options are required:

- `--path`
- `--line`
- `--line-type`

## Output Contracts

### Text Diff

Default `bitbucket pr diff` output continues to return a textual unified diff.
TTY output may remain colorized through the existing renderer path.

Raw output for default diff mode continues to expose the provider response for
the text diff path. This avoids breaking scripts that already call:

```bash
atlassian bitbucket pr diff DEMO example-repo 42 --output raw-json
```

### Line-Aware Diff

`bitbucket pr diff --with-lines --output json` should return stable normalized
data shaped like this:

```json
{
  "id": 42,
  "files": [
    {
      "path": "example.py",
      "hunks": [
        {
          "source_start": 10,
          "source_span": 2,
          "destination_start": 10,
          "destination_span": 3,
          "lines": [
            {
              "type": "ADDED",
              "old_line": null,
              "new_line": 12,
              "text": "+example response",
              "anchor": {
                "path": "example.py",
                "line": 12,
                "line_type": "ADDED"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

The exact raw Bitbucket JSON structure may differ by Server/Data Center version.
The normalized output should preserve the fields needed for inline comments and
keep unrecognized raw details available through `raw-json` and `raw-yaml`.

Line type normalization:

- added lines use `ADDED` and anchor against the destination line;
- removed lines use `REMOVED` and anchor against the source line;
- context lines use `CONTEXT` when Bitbucket returns enough metadata for a
  valid anchor;
- metadata lines do not get anchors.

### Inline Comment

An inline comment response keeps the existing normalized comment schema and
includes the returned anchor when Bitbucket provides it:

```json
{
  "id": "1001",
  "version": 1,
  "text": "example comment",
  "anchor": {
    "path": "example.py",
    "line": 12,
    "line_type": "ADDED"
  }
}
```

## Architecture

Keep the existing layering:

```text
Typer command -> service -> provider -> schema -> renderer
```

### Provider

Extend the Bitbucket provider protocol with structured diff and anchored comment
support:

```text
get_pull_request_diff(project_key, repo_slug, pr_id) -> str
get_pull_request_diff_with_lines(project_key, repo_slug, pr_id) -> dict
add_pull_request_comment(..., parent_id=None, anchor=None) -> dict
```

`get_pull_request_diff` continues to call the text `.diff` endpoint with
`Accept: text/plain`.

`get_pull_request_diff_with_lines` should call the JSON pull request diff API and
return the unmodified provider payload. The service owns normalization so the
provider remains close to transport behavior.

`add_pull_request_comment` should post directly to the pull request comments
endpoint when an anchor is supplied. The current `atlassian-python-api` helper
only accepts comment text and optional parent id, so anchored comments need a
small direct POST payload:

```json
{
  "text": "example comment",
  "anchor": {
    "path": "example.py",
    "line": 12,
    "lineType": "ADDED"
  }
}
```

The existing SDK helper can still be used for unanchored top-level comments and
replies, or the provider can use one direct POST path for all add variants as
long as behavior stays identical.

### Service

`PullRequestService` adds a `diff_with_lines` method that:

1. fetches provider JSON diff;
2. normalizes files, hunks, and lines;
3. derives `anchor` objects only for commentable lines;
4. returns a stable dictionary with the pull request id and file list.

`PullRequestCommentService.add` accepts an optional anchor argument. It delegates
to the provider and continues to normalize the result through
`BitbucketPullRequestComment`.

### Commands

`bitbucket pr diff` gains a `--with-lines` boolean option. When present, the
command calls `diff_with_lines` for normalized output and
`diff_with_lines_raw` for raw output. When absent, the command follows the
current text diff flow.

`bitbucket pr comment add` gains optional `--path`, `--line`, and `--line-type`
options. The command validates completeness and basic value shape, then passes a
normalized anchor dictionary to the service.

## Data Flow

Line-aware diff flow:

1. User calls `bitbucket pr diff ... --with-lines`.
2. Command selects structured diff mode.
3. Service asks the provider for Bitbucket JSON diff.
4. Provider calls the JSON diff endpoint with the authenticated Bitbucket
   session.
5. Service normalizes files, hunks, and lines and attaches reusable anchor
   dictionaries to commentable lines.
6. Renderer outputs markdown, JSON, YAML, raw JSON, or raw YAML.

Inline comment flow:

1. User calls `bitbucket pr comment add ... --path ... --line ... --line-type`.
2. Command validates that the inline option group is complete.
3. Service passes text plus anchor to the provider.
4. Provider POSTs a Bitbucket comment payload with `text` and `anchor`.
5. Service normalizes the returned comment and includes the returned anchor.
6. Renderer outputs the result in the selected mode.

## Error Handling

`--with-lines` must fail clearly when the structured diff API is unavailable or
returns an unexpected payload. It should not silently fall back to text diff
because that would produce output without reliable inline-comment coordinates.

Inline comment option validation:

- `--path`, `--line`, and `--line-type` must be supplied together;
- `--line` must be a positive integer;
- `--line-type` accepts `ADDED`, `REMOVED`, and `CONTEXT`.

`CONTEXT` is included because Bitbucket may support context-line anchors. If the
live Server/Data Center environment rejects context-line inline comments, the
implementation may narrow accepted values to `ADDED` and `REMOVED` and update
the spec before implementation continues.

If Bitbucket rejects an inline comment because the path, line, line type,
permissions, or pull request state are invalid, the CLI should surface the
server error through the existing error path. The CLI should not retry against a
different line type or guessed coordinate.

## Testing

Unit coverage:

- provider text diff still calls the text `.diff` endpoint;
- provider structured diff calls the JSON diff endpoint;
- provider inline comment creation sends a payload with `text` and `anchor`;
- provider unanchored comment creation remains compatible;
- service structured diff normalization maps Bitbucket files, hunks, and lines
  to stable output;
- service adds anchors only for commentable lines;
- command `pr diff --with-lines --output json` calls structured diff service;
- command `pr diff` without `--with-lines` preserves current behavior;
- command `pr comment add` without inline options preserves current behavior;
- command `pr comment add` with complete inline options succeeds;
- command `pr comment add` with partial inline options fails before building the
  service.

Documentation and sample-data coverage:

- update README examples for `pr diff --with-lines`;
- update README examples for inline `pr comment add`;
- keep project, repo, and comment examples on approved public placeholders such
  as `DEMO`, `example-repo`, and `example comment`;
- keep file path examples generic and non-real, for example `example.py`;
- scan README, docs, tests, examples, and sample payloads for real-looking
  identifiers before finishing.

Live e2e coverage:

- extend the existing Bitbucket branch and pull request round trip;
- create a pull request that changes a small generated file;
- call `bitbucket pr diff ... --with-lines --output json`;
- find an `ADDED` line anchor for that generated file;
- call `bitbucket pr comment add` with the returned path, line, and line type;
- assert the returned comment includes matching `anchor.path`, `anchor.line`,
  and `anchor.line_type`;
- delete the inline comment during existing cleanup where possible.

Repository verification after implementation:

```bash
ruff format --check .
python -m pytest -q
ruff check README.md pyproject.toml src tests docs
ATLASSIAN_E2E=1 python -m pytest tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live -q
```

If live credentials or the Bitbucket e2e environment are unavailable, the
feature cannot be called live-verified.

## Acceptance Criteria

- `bitbucket pr diff` default output is backward compatible.
- `bitbucket pr diff --with-lines --output json` exposes stable per-line
  coordinates and anchors for commentable lines.
- `bitbucket pr comment add` creates top-level comments when inline options are
  omitted.
- `bitbucket pr comment add` creates inline comments when `--path`, `--line`,
  and `--line-type` are supplied.
- Partial inline option groups fail with a CLI parameter error before any API
  request.
- Normalized comment output includes returned inline anchor metadata.
- README, tests, and live e2e coverage reflect the new behavior.
