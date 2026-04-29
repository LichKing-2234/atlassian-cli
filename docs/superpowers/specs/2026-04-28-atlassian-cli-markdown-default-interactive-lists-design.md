# Atlassian CLI Markdown-Default And Interactive Lists Design

## Summary

Replace the CLI's current human-facing `table` output model with a new default built around markdown and interactive terminal browsing.

`table` output should be removed from the CLI contract entirely. Human-oriented output should default to markdown for single-resource and write-result commands, while collection-oriented commands should enter an interactive list browser when running in a TTY and fall back to static markdown when running in a non-interactive environment.

This design explicitly supersedes the earlier table-readability direction. The goal is not to rescue table rendering. The goal is to replace it with a better human interaction model.

## Superseded Design

This design supersedes `docs/superpowers/specs/2026-04-27-atlassian-cli-table-output-readability-design.md`.

That earlier spec is obsolete and should not guide future implementation work.

## Goals

- Remove `table` from the supported output contract.
- Change the default human-readable output mode from `table` to `markdown`.
- Make collection commands (`list`, `search`) interactive by default in a TTY.
- Preserve static, deterministic output for non-TTY, redirected, and piped usage.
- Keep machine-readable output modes available and non-interactive.
- Keep normalized output contracts explicit and testable at the service/schema boundary.

## Non-Goals

- Preserving `table` as a compatibility alias.
- Designing a large full-screen terminal dashboard.
- Adding edit, merge, delete, or transition actions inside the interactive browser in phase 1.
- Replacing `json`, `yaml`, `raw-json`, or `raw-yaml`.
- Building remote fuzzy-search or server-backed incremental filtering in phase 1.
- Supporting clipboard integration, multi-select, or bulk actions in phase 1.

## Breaking Change

This is an intentional breaking change.

The CLI contract changes in these ways:

- `--output table` is removed.
- default output becomes `markdown`.
- TTY collection commands may no longer print static output by default; they may enter an interactive browser instead.

There is no planned compatibility shim for `table`. The old mode name should disappear rather than silently doing something different.

## Output Contract

Supported output values become:

- `markdown`
- `json`
- `yaml`
- `raw-json`
- `raw-yaml`

Mode semantics:

- `markdown`: human-readable normalized output
- `json`: normalized machine-readable output
- `yaml`: normalized machine-readable output
- `raw-json`: raw provider response serialized as JSON
- `raw-yaml`: raw provider response serialized as YAML

`markdown` is the default output mode.

## Human Output Behavior

Human-readable behavior depends on both command shape and terminal environment.

### Single-resource and write-result commands

Commands such as `get`, `create`, `update`, `delete`, `transition`, `merge`, `upload`, and `download` should default to static markdown output.

This behavior should be the same in both TTY and non-TTY contexts unless the user explicitly requests a machine-readable mode.

### Collection commands

Commands such as `list` and `search` should have two default behaviors:

- in a TTY: launch an interactive list browser
- in a non-TTY environment: emit static markdown summary output

Examples of collection commands in the current CLI include:

- `jira issue search`
- `jira project list`
- `jira user search`
- `confluence space list`
- `confluence attachment list`
- `bitbucket project list`
- `bitbucket repo list`
- `bitbucket branch list`
- `bitbucket pr list`

## TTY Detection And Fallback

Interactive behavior must be gated by terminal capability.

The CLI should only enter the interactive browser when all of the following are true:

- the selected mode is the default human mode (`markdown`)
- the command is a collection command
- stdout is a TTY
- stdin is a TTY
- the interactive browser initializes successfully

If any of those conditions fail, the CLI must fall back to static markdown output.

If the browser fails to initialize at runtime, the CLI should degrade gracefully to markdown instead of exiting with an interactive-only failure.

## Machine-Readable Modes

`json`, `yaml`, `raw-json`, and `raw-yaml` must never trigger the interactive browser.

They should always write deterministic serialized output to stdout.

This preserves scriptability and pipeline safety.

## Markdown Output Design

`markdown` is not a thin wrapper around JSON. It is a stable human-readable rendering contract.

Two markdown shapes are required:

- summary markdown for collection commands in non-TTY contexts
- detail markdown for single-resource and write-result commands

### Summary markdown for collections

Collection markdown should:

- use numbered records
- render one compact block per result
- show only high-value summary fields
- keep field ordering stable within a resource type
- summarize long list fields instead of expanding them fully

Example shape:

```md
1. PR #24996 - [FIX] ENG-23456: add che.audio.select_mic_orientation for iOS
   - State: OPEN
   - Author: 钟环
   - Reviewers: SDK, haolianfu, shenxuebo, +3 more
   - From: jira/ENG-23456/release/4.6
   - To: release/4.6
   - Updated: 2026-04-27 14:19:03
```

Collection markdown should not dump full descriptions, transport metadata, or raw nested provider objects unless the resource type has no better concise summary.

### Detail markdown for single objects and write results

Detail markdown should:

- start with a title line
- show stable metadata bullets near the top
- render long text in dedicated sections
- render nested objects as small subsections or bullets
- avoid raw JSON unless explicitly in machine-readable modes

Example shape:

```md
# PR #24996
[FIX] ENG-23456: add che.audio.select_mic_orientation for iOS

- State: OPEN
- Author: 钟环
- From: jira/ENG-23456/release/4.6
- To: release/4.6
- Updated: 2026-04-27 14:19:03

## Reviewers
- SDK
- haolianfu
- shenxuebo

## Description
...
```

## Interactive List Browser

The interactive browser is only for collection commands.

It should provide a lightweight terminal browsing experience rather than a heavy full-screen application.

### Phase-1 interaction model

List view:

- Up/Down or `j`/`k` to move selection
- `PageUp`/`PageDown` or `n`/`p` to move through pages
- `Enter` to open detail view for the selected item
- `/` to filter currently loaded results
- `r` to refresh the current page
- `q` to exit

Detail view:

- render the selected item using the detail markdown shape
- allow vertical scrolling
- `b` or `Esc` to return to the list

### Phase-1 scope limits

The browser should be read-only in phase 1.

It should not support:

- merge
- transition
- delete
- update
- bulk actions
- multi-select
- copy to clipboard

## Paging Strategy

The browser should not fetch all results up front.

It should layer terminal navigation on top of service-backed pagination:

- initially request only the first page
- request later pages when the user advances beyond the loaded range
- cache loaded pages within the session for back-navigation
- keep filtering local to already-loaded data in phase 1

This keeps the browser responsive and avoids high-latency or high-volume fetches for large repositories and searches.

## Command Behavior Matrix

### Default mode (`markdown`)

- collection command + TTY: interactive browser
- collection command + non-TTY: summary markdown
- single-resource or write-result command: detail markdown

### Explicit machine-readable mode

- `json`: normalized JSON
- `yaml`: normalized YAML
- `raw-json`: raw provider JSON
- `raw-yaml`: raw provider YAML

No interactive path should exist for these explicit modes.

## Architecture

The current generic output renderer should be restructured around markdown and machine serializers instead of table rendering.

Suggested responsibilities:

### Output mode layer

Owns:

- supported output mode parsing
- human-vs-machine mode classification
- interactive-eligibility checks

### Markdown rendering layer

Owns:

- summary markdown rendering for collections
- detail markdown rendering for single resources and write results
- stable field ordering and section shaping

### Interactive browser layer

Owns:

- TTY interaction loop
- selection state
- service-backed page loading
- detail view transitions
- graceful fallback behavior

### Command and service layer

Owns:

- whether a command is collection-shaped or single-resource-shaped
- how to fetch summary pages
- how to fetch full detail for a selected item when needed

The renderer and browser should remain generic. Product-specific field decisions should still come from normalized schema/service boundaries, not from ad hoc output hacks.

## File And Contract Impact

The implementation should expect changes in at least these areas:

- `src/atlassian_cli/cli.py`
- `src/atlassian_cli/config/models.py`
- `src/atlassian_cli/output/modes.py`
- `src/atlassian_cli/output/renderers.py`
- new modules for markdown rendering, TTY detection, and interactive browsing
- product command modules for collection-command interactive branching
- representative service modules where list/search and get need cleaner summary/detail separation
- `README.md`
- command help text and tests tied to output mode values

## Spec And Documentation Updates

This design requires follow-on updates to existing documentation:

- `docs/superpowers/specs/2026-04-18-atlassian-cli-design.md`
  - remove statements that read commands default to `table`
- `docs/superpowers/specs/2026-04-20-atlassian-cli-simplified-output-design.md`
  - replace `table` semantics with `markdown` plus interactive collection behavior
- `README.md`
  - update examples, supported output modes, and human-output explanation

## Phased Delivery

### Phase 1

- remove `table`
- make `markdown` the default output mode
- add markdown rendering for summary and detail views
- add TTY detection and interactive browser scaffolding
- connect interactive browsing for one or more representative collection commands
- add graceful non-TTY fallback

### Phase 2

- expand interactive browsing across all collection commands
- refine pagination caching and filtering behavior
- complete doc/help updates across all surfaces

This split reduces implementation risk while still landing the contract change early.

## Testing

Coverage should include:

### Output mode contract

- `table` is rejected as an invalid output mode
- `markdown` is accepted and becomes the default
- machine-readable modes still serialize deterministically

### TTY behavior

- collection commands in a TTY enter the interactive path
- collection commands in a non-TTY environment render summary markdown
- browser initialization failure falls back to markdown

### Markdown rendering

- collection markdown uses stable summary blocks
- detail markdown uses stable headings, bullets, and sections
- long lists summarize as `+N more` rather than expanding without bound

### Interactive browser

- selection movement works
- page advancement loads later service pages
- opening detail and returning to the list works
- quitting exits cleanly

### Command contract

- representative commands preserve full normalized output in `json` and `yaml`
- human-readable default behavior changes without affecting machine-readable output

## Acceptance Criteria

- `table` no longer exists as a supported output mode
- default output mode is `markdown`
- collection commands launch an interactive browser in a TTY and fall back to static markdown outside a TTY
- non-collection commands render stable detail markdown by default
- `json`, `yaml`, `raw-json`, and `raw-yaml` remain non-interactive and deterministic
- existing machine-readable normalized contracts remain explicit and testable
