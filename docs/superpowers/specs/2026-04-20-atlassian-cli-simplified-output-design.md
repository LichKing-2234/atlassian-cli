# Atlassian CLI Simplified Output Design

## Summary

Change the CLI so `json` and `yaml` output modes return simplified, stable resource-shaped payloads by default, while adding `raw-json` and `raw-yaml` for users who need the original provider response.

This keeps the default machine-readable output compact and predictable, closer to the `mcp-atlassian` model-first approach, without removing access to raw data for debugging.

## Goals

- Make `--output json` return simplified resource-shaped payloads by default.
- Make `--output yaml` render the same simplified payloads.
- Add `--output raw-json` and `--output raw-yaml` to expose original provider responses.
- Apply the output policy consistently to both read and write commands.
- Keep `table` output behavior unchanged.

## Non-Goals

- Rebuilding the entire CLI around the full `mcp-atlassian` model system.
- Hiding all nested structure. Small, intentional nested objects are allowed.
- Preserving exact current JSON structure for backward compatibility.
- Introducing resource-specific output selection flags beyond the new raw output modes.

## Output Modes

Supported output values become:

- `table`
- `json`
- `yaml`
- `raw-json`
- `raw-yaml`

Mode semantics:

- `table`: render the simplified payload as a table when table rendering is meaningful
- `json`: render the simplified payload as JSON
- `yaml`: render the simplified payload as YAML
- `raw-json`: render the original provider response as JSON
- `raw-yaml`: render the original provider response as YAML

## Simplification Strategy

### Core rule

Do not try to trim payloads in the renderer. The renderer should only serialize data it is given.

Instead:

- providers keep returning raw responses from `atlassian-python-api`
- services convert raw responses into simplified domain-shaped dictionaries for normal output
- commands choose simplified or raw service methods based on the selected output mode

This keeps output shaping explicit and testable at the resource boundary.

### Payload rules

Default simplified payloads should:

- include identifiers, titles, names, states, timestamps, and other directly useful fields
- allow small nested sub-objects when they improve clarity
- exclude obviously noisy transport or SDK structures such as `_expandable`, `_links`, `avatarUrls`, whole `fields` blobs, whole `body` blobs, and raw user/reviewer objects
- avoid leaking entire raw responses through nested fields by accident

### Read vs write operations

Read operations:

- `list` and `search` return summary-oriented records
- `get` returns detail-oriented records, still simplified

Write operations:

- `create`, `update`, `delete`, `transition`, `merge`, and similar commands return concise result payloads that reflect the operation outcome
- these commands must not default to dumping the raw API response body unless `raw-json` or `raw-yaml` is explicitly requested

## Scope

This change covers all current product commands:

### Jira

- `issue get`
- `issue search`
- `issue create`
- `issue update`
- `issue transition`
- `project list`
- `project get`
- `user get`
- `user search`

### Confluence

- `page get`
- `page create`
- `page update`
- `page delete`
- `space list`
- `space get`
- `attachment list`
- `attachment upload`
- `attachment download`

### Bitbucket

- `project list`
- `project get`
- `repo list`
- `repo get`
- `repo create`
- `branch list`
- `pr list`
- `pr get`
- `pr create`
- `pr merge`

## Suggested Output Shapes

### Jira issue

Example simplified `json`:

```json
{
  "key": "DEMO-10001",
  "summary": "Example work item summary",
  "status": { "name": "Done" },
  "assignee": { "display_name": "Example Author" },
  "reporter": { "display_name": "reviewer-one" },
  "priority": { "name": "Highest" },
  "updated": "2025-10-11T06:39:12.513+0000"
}
```

### Confluence page

Example simplified `json`:

```json
{
  "id": "668233149",
  "title": "Example Page",
  "space": { "key": "DEMO", "name": "Demo Project" },
  "version": 34
}
```

### Bitbucket pull request

Example simplified `json`:

```json
{
  "id": 42,
  "title": "Example pull request",
  "state": "OPEN",
  "author": { "display_name": "Example Author" },
  "from_ref": { "display_id": "feature/DEMO-1234/example-change" },
  "to_ref": { "display_id": "main" },
  "reviewers": [
    { "display_name": "reviewer-one", "approved": true }
  ]
}
```

These examples are directional. Exact fields may vary by command, but the design intent is stable, compact, resource-shaped output.

## Architecture

### Render layer

`output/renderers.py` and `output/formatters.py` should:

- recognize the new `raw-json` and `raw-yaml` modes
- keep serialization generic
- avoid resource-specific field filtering logic

### Service layer

Services should become the main output shaping boundary:

- normal service methods return simplified payloads
- raw service methods or equivalent command-path helpers return original provider data for raw modes

Where schema models already exist, prefer using them to define the simplified output shape instead of ad hoc field copies.

### Schema layer

Extend existing schema models or add missing ones so more resources have explicit simplified dictionaries, similar in spirit to `mcp-atlassian`'s `to_simplified_dict()` pattern.

The local codebase does not need to mirror the full `mcp-atlassian` model hierarchy, but it should borrow the principle:

- parse raw API response
- keep only meaningful fields
- serialize via explicit schema/model boundaries

## Testing

Add tests for:

- `render_output(..., output=\"raw-json\")`
- `render_output(..., output=\"raw-yaml\")`
- simplified vs raw output for representative Jira, Confluence, and Bitbucket commands
- read command payloads no longer containing noisy raw-only fields by default
- write command payloads returning concise simplified results by default
- raw modes preserving original provider response structure

Representative command coverage should include:

- Jira issue get
- Jira project list
- Confluence page get
- Confluence space list
- Bitbucket project list
- Bitbucket pr get
- one or more write operations such as Jira issue create and Bitbucket pr merge

## Documentation

Update `README.md` and CLI help text to explain:

- `json` and `yaml` now return simplified payloads
- `raw-json` and `raw-yaml` are available for debugging and full-fidelity inspection
- users who previously depended on raw `json` should switch to `raw-json`
