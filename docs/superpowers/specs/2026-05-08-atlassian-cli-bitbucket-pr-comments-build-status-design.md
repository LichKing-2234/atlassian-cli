# Atlassian CLI Bitbucket PR Comments and Build Status Design

## Summary

Extend the Bitbucket command surface with two first-phase workflow capabilities:

- full pull request comment management by comment id and version
- build status lookup from both pull request and commit perspectives

Keep `bitbucket pr get` lightweight. It should continue to return only pull request metadata. Comments and build statuses are intentionally exposed through dedicated commands because they require extra API calls, paging, and permissions.

## Goals

- Add `bitbucket pr comment` commands for listing, reading, adding, replying to, editing, and deleting pull request comments.
- Add `bitbucket pr build-status` to summarize build statuses for commits associated with a pull request.
- Add `bitbucket commit build-status` to inspect build statuses for an explicit commit hash.
- Preserve raw output modes for troubleshooting original Bitbucket responses.
- Keep the command, service, provider, and schema layering consistent with the existing Bitbucket implementation.
- Update tests, README examples, and live e2e coverage ownership for every new CLI leaf command.

## Non-Goals

- Adding `--include comments` or `--include build-status` to `bitbucket pr get`.
- Loading comments or build statuses in the interactive `bitbucket pr list` detail view.
- Adding a unified pull request activity dashboard.
- Adding tasks, approve or unapprove, can-merge, participants, or default reviewers.
- Adding anchored inline comment creation in the first phase.
- Adding Bitbucket Cloud support.

Existing inline comments should still be listable, readable, editable, and deletable when Bitbucket returns them through the pull request comments API. Creating new comments in phase one is limited to top-level text comments and replies because inline anchoring requires extra file and diff coordinate semantics.

## Command Shape

Pull request comment commands:

```bash
atlassian bitbucket pr comment list DEMO example-repo 42
atlassian bitbucket pr comment get DEMO example-repo 42 1001
atlassian bitbucket pr comment add DEMO example-repo 42 "example comment"
atlassian bitbucket pr comment reply DEMO example-repo 42 1001 "example response"
atlassian bitbucket pr comment edit DEMO example-repo 42 1001 "example comment" --version 3
atlassian bitbucket pr comment delete DEMO example-repo 42 1001 --version 3
```

Build status commands:

```bash
atlassian bitbucket pr build-status DEMO example-repo 42
atlassian bitbucket pr build-status DEMO example-repo 42 --latest-only
atlassian bitbucket commit build-status abc123
```

All commands support the existing output modes:

- `markdown`
- `json`
- `yaml`
- `raw-json`
- `raw-yaml`

## Output Contracts

### Pull Request Comments

Normalized comment output should use stable field names:

```json
{
  "id": "1001",
  "version": 3,
  "text": "example comment",
  "author": {
    "display_name": "Example Author",
    "name": "example-user-id"
  },
  "created_date": "1704153600000",
  "updated_date": "1704153600000",
  "parent": {
    "id": "1000"
  },
  "anchor": {
    "path": "src/example.py",
    "line": 12
  }
}
```

`list` should return a collection envelope:

```json
{
  "results": [
    {
      "id": "1001",
      "version": 3,
      "text": "example comment"
    }
  ],
  "start_at": 0,
  "max_results": 25
}
```

Markdown list output should show a compact summary with id, version, author, updated date, and a short text preview. Markdown detail output should include the full text and parent or anchor metadata when present.

### Build Status

Commit build status output should use:

```json
{
  "commit": "abc123",
  "overall_state": "SUCCESSFUL",
  "results": [
    {
      "key": "DEMO",
      "name": "Example build",
      "state": "SUCCESSFUL",
      "url": "https://bitbucket.example.com/build/DEMO",
      "description": "example response",
      "date_added": "1704153600000"
    }
  ]
}
```

Pull request build status output should include per-commit summaries:

```json
{
  "pull_request": {
    "id": 42,
    "project_key": "DEMO",
    "repo_slug": "example-repo"
  },
  "overall_state": "FAILED",
  "commits": [
    {
      "commit": "abc123",
      "overall_state": "FAILED",
      "results": []
    }
  ]
}
```

The overall state precedence is:

1. `FAILED`
2. `INPROGRESS`
3. `SUCCESSFUL`
4. `UNKNOWN`

Any unknown state from Bitbucket should be preserved in the raw item and treated as `UNKNOWN` for summary purposes.

## Architecture

Keep the existing command flow:

```text
Typer command -> service -> provider -> schema -> renderer
```

### Commands

Add a pull request comment command module, for example:

```text
src/atlassian_cli/products/bitbucket/commands/pr_comment.py
```

Register it under the existing pull request command group as:

```text
bitbucket pr comment ...
```

Add a build status command module, for example:

```text
src/atlassian_cli/products/bitbucket/commands/build_status.py
```

Wire `pr build-status` through the existing pull request command group and add a new `bitbucket commit` command group for `commit build-status`.

### Services

Add focused services:

- `PullRequestCommentService`
- `BuildStatusService`

`PullRequestCommentService` owns comment normalization, paging envelopes, and pass-through of `version` for edit and delete operations.

`BuildStatusService` owns:

- querying one commit's build statuses
- querying pull request commits
- choosing latest commit behavior when `--latest-only` is set
- aggregating per-commit states into a pull request summary

### Provider

Extend `BitbucketProvider` with methods for:

- listing pull request comments
- getting one pull request comment
- adding a pull request comment
- updating a pull request comment
- deleting a pull request comment
- listing pull request commits
- getting associated build statuses for a commit

For Bitbucket Server/Data Center, reuse public `atlassian-python-api` methods where available:

- `add_pull_request_comment`
- `get_pull_request_comment`
- `update_pull_request_comment`
- `delete_pull_request_comment`
- `get_pull_requests_commits`
- `get_associated_build_statuses`

The SDK exposes pull request comment URL helpers but does not expose a dedicated public list wrapper. The provider should call the pull request comments endpoint through the SDK HTTP client for `list_pull_request_comments`, preserving normal auth and header injection behavior.

### Schemas

Add small models in `src/atlassian_cli/products/bitbucket/schemas.py`:

- `BitbucketPullRequestComment`
- `BitbucketBuildStatus`
- `BitbucketCommitBuildStatusSummary`
- `BitbucketPullRequestBuildStatusSummary`

These models should tolerate missing optional fields because Bitbucket Server/Data Center responses vary by version and plugin configuration.

## Error Handling

`edit` and `delete` require `--version`. The CLI should fail before making an API call when the option is missing.

If a pull request has no commits, `pr build-status` returns:

```json
{
  "overall_state": "UNKNOWN",
  "commits": []
}
```

If a commit has no build statuses, the command returns an empty `results` list and `overall_state: "UNKNOWN"`.

If one commit build status lookup fails during `pr build-status`, the command fails. The first phase should not hide a CI visibility problem behind a partial summary. A future `--best-effort` option can be considered separately.

Cloud remains unsupported through the existing v1 provider selection behavior.

## Documentation

Update README with examples for:

- listing pull request comments
- adding and replying to pull request comments
- editing and deleting comments with `--version`
- checking pull request build status
- checking commit build status

All examples must use the approved neutral placeholder set, including `DEMO`, `example-repo`, `Example Author`, `example comment`, `example response`, and `example-user-id`.

## Testing

### Unit Tests

Add command tests for:

- `bitbucket pr comment list`
- `bitbucket pr comment get`
- `bitbucket pr comment add`
- `bitbucket pr comment reply`
- `bitbucket pr comment edit`
- `bitbucket pr comment delete`
- `bitbucket pr build-status`
- `bitbucket pr build-status --latest-only`
- `bitbucket commit build-status`

Add service tests for:

- comment collection envelopes
- comment normalization with parent and anchor fields
- edit and delete version forwarding
- commit build status state aggregation
- pull request build status aggregation across multiple commits
- empty commit and empty build-status behavior

Add provider tests for:

- comments list endpoint construction
- comment add/get/update/delete method forwarding
- pull request commits paging materialization
- associated build status lookup

Add schema tests for missing optional author, parent, anchor, URL, and timestamp fields.

### Live E2E Tests

Update `tests/e2e/coverage_manifest.py` for every new leaf command.

Extend the existing Bitbucket live pull request round-trip test:

1. create a temporary branch and pull request
2. add a top-level pull request comment
3. list comments and find the added comment
4. get the comment by id
5. reply to the comment
6. edit the top-level comment with its current version
7. delete the reply or edited comment with its current version
8. call `pr build-status` and assert the normalized structure
9. call `commit build-status` for the pull request head commit and assert the normalized structure
10. merge the pull request as the existing test already does

Build status e2e should not require the live repository to have a real CI system. It should verify command execution and response shape, allowing empty results and `UNKNOWN`.

## Risks

- Pull request comment payloads vary across Bitbucket versions, especially for inline anchors.
- Comment `edit` and `delete` require the latest server version. Users may need to call `get` before mutating an older comment.
- PR build status can require several API calls for large pull requests.
- Some Bitbucket instances may restrict build-status visibility independently from pull request visibility.

The design accepts these risks because the commands are explicit and do not affect existing fast metadata paths.

## Success Criteria

- `bitbucket pr get` remains lightweight and does not fetch comments or build statuses.
- `bitbucket pr comment` supports list, get, add, reply, edit, and delete.
- `bitbucket pr build-status` summarizes pull request commit build statuses.
- `bitbucket commit build-status` returns commit-specific build statuses.
- New commands are represented in the e2e coverage manifest.
- README examples use only neutral public placeholders.
- Repository verification passes with `ruff format --check .`, `python -m pytest -q`, and `ruff check README.md pyproject.toml src tests docs`.
