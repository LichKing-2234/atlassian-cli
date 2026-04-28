# Atlassian CLI Full E2E Coverage Design

## Summary

Add a local-only live end-to-end test suite that covers every CLI subcommand with at least one real command chain against real Atlassian Server/Data Center instances.

The suite should:

- execute the real CLI through `python -m atlassian_cli.main`
- reuse the operator's existing local CLI config unless `ATLASSIAN_CONFIG_FILE` overrides it
- use dedicated live resources for write operations
- clean up created resources with best-effort teardown and explicit residue reporting
- maintain a coverage manifest so new CLI subcommands cannot be added without live e2e ownership

This design explicitly treats "covered by e2e" as:

- every CLI subcommand is invoked by at least one live test
- supported write commands perform real remote mutations and cleanup
- unsupported commands still have a live CLI contract test that asserts the expected failure mode

## Goals

- Cover every existing CLI subcommand with at least one live test.
- Keep the live suite local-only and opt-in.
- Make failures easy to localize by splitting tests by product area.
- Minimize live resource sprawl by reusing a small number of temporary resources per product.
- Prevent future command additions from silently bypassing e2e coverage.

## Non-Goals

- Exhaustively test every output mode in live e2e.
- Run live e2e in default CI.
- Add concurrent execution for live tests.
- Replace existing unit, command, or integration tests.

## Scope

The current CLI surface to cover is:

- Jira
  - `issue get`
  - `issue search`
  - `issue create`
  - `issue update`
  - `issue transition`
  - `issue transitions`
  - `issue delete`
  - `issue batch-create`
  - `issue changelog-batch`
  - `field search`
  - `field options`
  - `comment add`
  - `comment edit`
  - `project list`
  - `project get`
  - `user get`
  - `user search`
- Confluence
  - `page get`
  - `page search`
  - `page children`
  - `page tree`
  - `page history`
  - `page diff`
  - `page move`
  - `page create`
  - `page update`
  - `page delete`
  - `comment list`
  - `comment add`
  - `comment reply`
  - `space list`
  - `space get`
  - `attachment list`
  - `attachment upload`
  - `attachment download`
- Bitbucket
  - `project list`
  - `project get`
  - `repo get`
  - `repo list`
  - `repo create`
  - `branch list`
  - `pr list`
  - `pr get`
  - `pr create`
  - `pr merge`

## Live Resource Contract

The live suite will use these operator-provided resources:

- Jira project: `EEP`
- Confluence space: `ADC`
- Bitbucket project key: `~luxuhui_agora.io`
- Bitbucket seed repository: `atlassian-cli-e2e-test`

The suite will assume:

- Confluence writes are allowed in `ADC`
- Jira issue creation and transition are allowed in `EEP`
- Bitbucket repository creation is allowed under `~luxuhui_agora.io`
- Bitbucket PR creation and merge are allowed in `atlassian-cli-e2e-test`
- test setup may use regular `git clone`, `git commit`, and `git push` for Bitbucket PR preparation

## Test Architecture

The live suite should live under `tests/e2e/` and be split by product instead of using one large serial script.

Planned structure:

- `tests/e2e/support/`
  - live CLI runner
  - environment loader
  - JSON parsing helpers
  - temporary file helpers
  - cleanup registry
  - Bitbucket git sandbox helpers
- `tests/e2e/coverage_manifest.py`
  - maps every CLI subcommand to at least one owning live test
- `tests/e2e/test_jira_live.py`
- `tests/e2e/test_confluence_live.py`
- `tests/e2e/test_bitbucket_live.py`
- `tests/e2e/test_coverage_manifest.py`
  - fails if the manifest and the discovered CLI subcommands diverge

This split keeps failures isolated by product while still allowing shared setup and consistent assertions.

## Execution Model

All live e2e coverage must invoke the real CLI process, not `CliRunner`.

The common execution helpers should provide:

- `run_cli(...)`
  - executes `python -m atlassian_cli.main`
  - injects `PYTHONPATH=src` for editable local execution
  - applies `ATLASSIAN_CONFIG_FILE` when present
  - returns stdout, stderr, and exit code
- `run_json(...)`
  - calls `run_cli(...)`
  - requires success
  - parses JSON stdout into Python data
- `run_failure(...)`
  - calls `run_cli(...)`
  - requires non-zero exit
  - asserts an expected error message fragment

Live e2e should default to `--output json` because it is the most stable assertion surface. Tests may use `--output raw-json` when a command's normalized representation omits fields needed for validation.

The suite should run serially. No live e2e test should assume parallel safety.

## Environment Variables

The live suite should be fully opt-in and local-only.

Required gating variables:

- `ATLASSIAN_E2E=1`

Optional config override:

- `ATLASSIAN_CONFIG_FILE=/path/to/config.toml`

Resource defaults:

- `ATLASSIAN_E2E_JIRA_PROJECT=EEP`
- `ATLASSIAN_E2E_CONFLUENCE_SPACE=ADC`
- `ATLASSIAN_E2E_BITBUCKET_PROJECT='~luxuhui_agora.io'`
- `ATLASSIAN_E2E_BITBUCKET_REPO=atlassian-cli-e2e-test`

The helper layer should centralize these values in a typed environment object so tests do not repeatedly parse raw environment strings.

## Resource Lifecycle

Every product test module should use a cleanup registry that tracks created resources and performs best-effort teardown in reverse order.

Rules:

- generated names must include a timestamp and random suffix
- cleanup must run in `finally` blocks or `yield` fixtures
- cleanup failures must be surfaced with concrete resource identifiers
- cleanup should never silently swallow remote residue

Examples:

- Jira issue keys created during `create` and `batch-create`
- Confluence page ids, comment ids, attachment metadata, and downloaded temp files
- Bitbucket repo slugs, PR ids, branch names, and temporary git sandboxes

## Coverage Strategy

The suite should prefer small scenario tests that each cover multiple related subcommands rather than one test per command.

### Jira coverage

`test_jira_project_and_metadata_live`

- covers `jira project list`
- covers `jira project get`
- covers `jira field search`
- covers `jira field options`
- covers `jira user get`
- covers `jira user search`

`test_jira_issue_round_trip_live`

- covers `jira issue create`
- covers `jira issue get`
- covers `jira issue update`
- covers `jira issue search`
- covers `jira issue transitions`
- covers `jira issue transition`
- covers `jira issue delete`
- covers `jira comment add`
- covers `jira comment edit`

`test_jira_issue_batch_create_live`

- covers `jira issue batch-create`

`test_jira_issue_changelog_batch_rejected_live`

- covers `jira issue changelog-batch`
- asserts the real CLI returns the current v1 rejection message for unsupported Cloud-only functionality

### Confluence coverage

`test_confluence_space_and_search_live`

- covers `confluence space list`
- covers `confluence space get`
- covers `confluence page search`
- covers `confluence page tree`

`test_confluence_page_round_trip_live`

- covers `confluence page create`
- covers `confluence page get`
- covers `confluence page update`
- covers `confluence page history`
- covers `confluence page diff`
- covers `confluence page delete`

`test_confluence_page_move_and_children_live`

- covers `confluence page children`
- covers `confluence page move`

`test_confluence_comment_round_trip_live`

- covers `confluence comment add`
- covers `confluence comment reply`
- covers `confluence comment list`

`test_confluence_attachment_round_trip_live`

- covers `confluence attachment upload`
- covers `confluence attachment list`
- covers `confluence attachment download`

### Bitbucket coverage

`test_bitbucket_project_and_repo_queries_live`

- covers `bitbucket project list`
- covers `bitbucket project get`
- covers `bitbucket repo list`
- covers `bitbucket repo get`

`test_bitbucket_repo_create_live`

- covers `bitbucket repo create`

`test_bitbucket_branch_and_pr_round_trip_live`

- covers `bitbucket branch list`
- covers `bitbucket pr list`
- covers `bitbucket pr get`
- covers `bitbucket pr create`
- covers `bitbucket pr merge`

## Product-Specific Resource Plans

### Jira

Jira live coverage should center on temporary issues in `EEP`.

- `issue create` creates a temporary issue
- `issue update` modifies summary and description
- `issue search` locates the created issue by a unique summary token
- `issue transitions` captures available transitions for the issue
- `issue transition` uses a discovered transition from the live list rather than hard-coding a transition name
- `comment add` and `comment edit` operate on the created issue
- `issue delete` removes the temporary issue
- `issue batch-create` uses a temporary JSON file containing multiple issues and then cleans up all created issue keys

`field options` must not hard-code a field id. The test should:

1. run `field search`
2. pick a field that exposes allowed values in `issue_createmeta` for `EEP` and a known issue type such as `Task`
3. assert the returned options list shape

`user get` should resolve a username discovered from `user search` rather than baking a person-specific identifier into the repository.

### Confluence

Confluence live coverage should center on temporary pages in `ADC`.

- one primary page for `create/get/update/history/diff/delete`
- one child page and one target page for `children/move`
- one or more comments attached to the primary page for `add/reply/list`
- one uploaded attachment for `upload/list/download`

`page diff` should compare versions created by a real `update`.

`page history` should assert that the reported version increments after update.

`attachment download` must verify the downloaded file exists and matches uploaded content.

### Bitbucket

Bitbucket live coverage needs both a fixed repository and temporary repositories.

Fixed repository:

- project key: `~luxuhui_agora.io`
- repo slug: `atlassian-cli-e2e-test`

Temporary repo:

- created by `bitbucket repo create`
- cleaned up out-of-band by test teardown through REST/SDK because the CLI has no repo delete command

PR flow:

1. clone the fixed repo into a temp sandbox
2. create a uniquely named branch
3. add a tiny file or edit a temporary fixture file
4. commit and push
5. run `bitbucket pr create`
6. run `bitbucket pr list`
7. run `bitbucket pr get`
8. run `bitbucket pr merge`
9. delete the temporary source branch in teardown if the server does not do so automatically

`branch list` should assert that the temporary branch appears after push.

## Coverage Manifest

`tests/e2e/coverage_manifest.py` should define a normalized list of CLI subcommands, for example:

- `jira issue get`
- `jira issue search`
- `confluence attachment download`
- `bitbucket pr merge`

Each entry should name the owning live test function.

A dedicated test should discover the current CLI subcommand set from the Typer app tree and compare it to the manifest.

This gives two guarantees:

- every existing command is assigned to a live test
- new commands force an explicit manifest update before tests pass

## Error Handling

Live e2e must favor diagnostic precision over abstraction.

Rules:

- include full command arguments in assertion failures
- include stdout and stderr on command failure
- surface parsed resource ids when cleanup fails
- keep assertions minimal and contract-oriented
- avoid broad retry loops unless a specific remote API is known to be eventually consistent

If eventual consistency becomes a real issue for search or branch visibility, retries should be narrowly targeted and documented at the specific assertion site.

## Implementation Gaps To Fix First

One current command cannot honestly count as covered by a real command chain:

- `confluence attachment download`

Today the provider returns a synthetic payload without downloading the file. Before full e2e coverage can be claimed, this command must be changed to perform a real download and return a payload derived from the real operation.

The design assumes this implementation fix is completed before the Confluence attachment live test is finalized.

## Documentation

README should be expanded from the current minimal e2e note to describe:

- the full live suite scope
- the required environment variables
- the dedicated live resources
- the fact that some tests perform real writes
- the cleanup model
- a recommended local invocation command

## Rollout Plan

Implementation should proceed in this order:

1. add the shared live e2e support layer and coverage manifest skeleton
2. fix `confluence attachment download` so it performs a real download
3. implement Jira live coverage
4. implement Confluence live coverage
5. implement Bitbucket git sandbox and live coverage
6. update README and any test registration needed for local use
7. run targeted local verification against the real configured instances

This order keeps the hardest and most instance-sensitive Bitbucket flow until the end while ensuring the one known fake path is corrected before claiming complete coverage.

## Verification Expectations

At minimum, completion should include:

- targeted unit coverage for any new helper modules
- targeted tests for the new real attachment download implementation
- successful local runs of the live e2e modules against the configured instances
- a passing coverage-manifest consistency test

## Risks

- Bitbucket personal project keys may not behave exactly like normal project keys for repo creation on all instances.
- Jira transition availability may vary by workflow state, so the test must discover a valid transition instead of assuming one.
- Confluence search and tree results may be subject to indexing or permission quirks, so assertions must stay minimal and scoped to created resources where possible.
- Live residue is possible when remote cleanup fails, so teardown logs must be explicit and actionable.

## Acceptance Criteria

- every CLI subcommand is listed in the coverage manifest
- every manifest entry maps to at least one live test
- supported write commands execute real mutations against the provided resources
- unsupported `jira issue changelog-batch` is covered by a live CLI contract test
- `confluence attachment download` performs a real download before the suite claims complete coverage
- the suite remains opt-in and local-only
