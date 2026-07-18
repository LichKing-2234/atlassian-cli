# gh-Compatible Bitbucket PR Edit Design

**Status:** Approved for implementation

**Baseline:** `gh v2.96.0` command grammar and observable behavior, limited only by
capabilities that Bitbucket Server/Data Center does not provide.

## Goal

Add `atlassian bitbucket pr edit` so users can update the Bitbucket fields that
have direct `gh pr edit` equivalents: title, body, destination branch, and
individual reviewers. Preserve the existing gh-compatible repository and pull
request selection behavior.

## Command Contract

```text
atlassian bitbucket pr edit [<number> | <url> | <branch>] [flags]
```

Registered flags:

```text
      --add-reviewer login      Add or re-request individual reviewers
  -B, --base branch             Change the destination branch
  -b, --body string             Set the new description
  -F, --body-file file          Read description from a file, or stdin with "-"
      --remove-reviewer login   Remove individual reviewers
  -t, --title string            Set the new title
  -R, --repo repository         Select another Bitbucket repository
```

Reviewer options accept repeated flags and comma-separated values, matching
`gh`. Values are normalized to a stable de-duplicated list while retaining the
first occurrence.

The following public `gh pr edit` flags are not registered because Bitbucket
Server/Data Center has no equivalent pull request concept:

- `--add-assignee` and `--remove-assignee`
- `--add-label` and `--remove-label`
- `--add-project` and `--remove-project`
- `--milestone` and `--remove-milestone`

Teams, group slugs, and Copilot are not accepted as reviewers. Bitbucket pull
request reviewers are individual user identities.

## Repository and Pull Request Selection

The command reuses the existing gh-compatible repository context and pull
request finder instead of accepting legacy positional project and repository
arguments.

- A numeric selector resolves that pull request in the selected repository.
- A Bitbucket pull request URL supplies both repository and pull request.
- A branch selector finds the best matching pull request using the existing
  open-first and newest-first ranking.
- An omitted selector infers the current branch, including when `--repo` is
  supplied. This is the `gh pr edit -R` exception already recorded in the
  parity specification.
- Repository and URL host mismatches fail before any update request.

## Input Behavior

`--body` and `--body-file` are mutually exclusive. The relation is validated
before repository discovery, file reads, or network access. `--body-file -`
reads stdin exactly once. An explicit empty `--title ""` or `--body ""` is an
edit, not an omitted value.

When at least one edit flag is provided, the command is non-interactive and
changes only the requested fields.

When no edit flags are provided:

- In a TTY, prompt for which supported fields to edit, seed prompts with the
  current values, and require at least one selected field before updating.
- In non-interactive mode, exit `1` with an actionable error requiring one of
  `--title`, `--body`, `--base`, `--add-reviewer`, or `--remove-reviewer`.
- Cancellation exits without sending an update.

The interactive flow stays inside a small prompt adapter so command and service
tests can inject deterministic answers without starting a real editor.

## Architecture

### Command Layer

`products/bitbucket/commands/pr.py` owns Typer grammar and orchestration:

1. Validate flag relations and parse body/reviewer input.
2. Resolve repository context and the pull request selector with existing
   gh-compatible helpers.
3. Collect interactive edits when needed.
4. Call the edit service.
5. Print only the updated pull request URL on success, matching `gh`.

The command does not construct Bitbucket update payloads.

### Edit Service

A focused `PullRequestEditService` owns fetch-modify-update behavior. It accepts
an immutable edit request whose optional values distinguish "not edited" from
"edited to an empty value."

The service:

1. Fetches the current raw pull request.
2. Applies only requested title, description, destination branch, and reviewer
   changes.
3. Preserves the source ref, destination repository, existing reviewers, and
   all untouched editable values.
4. Sends one update through the provider.
5. Returns the updated raw pull request for URL rendering.

This boundary keeps selector, TTY, and output concerns out of payload logic and
makes optimistic-concurrency behavior directly testable.

### Provider Layer

Extend `BitbucketProvider` with:

```python
def update_pull_request(
    self,
    project_key: str,
    repo_slug: str,
    pr_id: int,
    payload: dict,
) -> dict: ...
```

The Server/Data Center provider delegates to the installed Atlassian client's
`update_pull_request()` method, which performs `PUT` on the pull request
resource. Cloud remains unsupported through the repository's existing provider
boundary.

## Update Payload and Concurrency

Bitbucket requires the current pull request `version`. Every update payload
contains the version returned by the immediately preceding GET. A stale version
failure is returned to the user; the command does not retry automatically and
risk overwriting a concurrent edit.

The payload contains the complete Bitbucket fields needed for an update:

```json
{
  "version": 7,
  "title": "Example pull request",
  "description": "example response",
  "fromRef": {"id": "refs/heads/feature/DEMO-1234/example-change"},
  "toRef": {
    "id": "refs/heads/main",
    "repository": {"slug": "example-repo", "project": {"key": "DEMO"}}
  },
  "reviewers": [{"user": {"name": "reviewer-one"}}]
}
```

The service derives this document from the raw GET response rather than from a
simplified schema so no required identity or ref data is lost.

## Reviewer Semantics

Reviewer comparisons use Bitbucket login identity in this order: `name`, then
`slug`, then `username`. Display names are never used as identifiers.

- Existing reviewer objects are preserved byte-for-byte when retained.
- Added logins become minimal `{"user": {"name": login}}` entries accepted by
  the Bitbucket update API.
- Removed logins are excluded from the final reviewer list.
- Additions and removals are de-duplicated. If the same login appears in both,
  removal wins so the final state is deterministic.
- Adding an existing reviewer and removing an absent reviewer are successful
  no-ops, consistent with desired-state editing.

The Bitbucket server validates that added logins exist and are eligible. Its
error response is preserved through the existing CLI error mapping.

## Errors and Side Effects

All local validation happens before the first network request. After resolution,
the command performs one GET and at most one PUT. There is no partial metadata
versus reviewer update because both are sent in the same Bitbucket document.

Expected failures include an unresolved repository, unmatched selector,
conflicting body sources, unreadable body file, non-TTY invocation without edit
flags, invalid reviewer identity, invalid destination branch, and stale version.
Failures do not print a success URL.

## Documentation and Coverage

Update user-facing Bitbucket PR documentation and README command examples with
only the approved neutral placeholders. Add `pr edit` to
`tests/e2e/coverage_manifest.py` and extend the existing Bitbucket live e2e path
to create a temporary pull request, edit reversible fields, verify the returned
state, and restore or delete the temporary resource during cleanup.

## Test Strategy

Follow red-green-refactor for each boundary:

- Provider tests prove exact delegation and payload preservation.
- Service tests cover each editable field, explicit empty values, unchanged
  fields, ref normalization, reviewer add/remove/no-op/conflict behavior, and
  use of the fetched version.
- Command tests cover help grammar, unsupported flag absence, selector forms,
  current-branch inference, `-R`, body precedence, stdin, comma/repeated reviewer
  values, interactive/non-interactive behavior, cancellation, error exits, and
  success URL output.
- The affected live e2e verifies the real Bitbucket PUT path with
  `ATLASSIAN_E2E=1`.
- Final repository verification runs `ruff format --check .`,
  `python -m pytest -q`, and
  `ruff check README.md pyproject.toml src tests docs` using the shared virtual
  environment and the worktree source path.
