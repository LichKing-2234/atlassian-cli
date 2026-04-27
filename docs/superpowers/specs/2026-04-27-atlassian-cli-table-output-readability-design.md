# Atlassian CLI Table Output Readability Design

## Summary

Improve `--output table` readability by rendering nested values as terminal-friendly summaries instead of raw Python structure representations.

The goal is not to redesign the normalized data model. The goal is to make the existing table view easier to scan in a terminal by turning common nested objects and lists into short, readable cell text.

## Goals

- Make common nested values readable in table output.
- Remove raw Python `dict` and `list` `repr` output from typical table cells.
- Preserve the current table row and column structure.
- Keep the renderer generic and product-agnostic.
- Keep `json`, `yaml`, `raw-json`, and `raw-yaml` behavior unchanged.

## Non-Goals

- Redesigning resource schemas for table-specific output.
- Adding resource-specific table columns such as `assignee_name` or `status_name`.
- Reordering or dropping existing normalized fields to create a compact summary table.
- Preserving the exact current textual representation of nested values in table mode.
- Expanding deep nested objects into multiple columns.

## Current Problem

The current table renderer converts every cell with `str(value)`.

That creates poor terminal output for normalized resource shapes that intentionally contain small nested objects and lists. Common examples include:

- `{"name": "In Progress"}`
- `{"display_name": "Alice Zhang", "email": "alice@example.com"}`
- `["prod", "sev1", "backend"]`

These values are technically correct but hard to scan in a fixed-width terminal. They also increase wrapping because the output includes braces, quotes, key names, and Python-specific formatting that do not add much value in a human-oriented table view.

## Design Principles

- `table` mode is a human-readable summary view, not a structure-preserving serialization format.
- The table renderer should summarize values, not reshape resources.
- The renderer must stay generic and must not know product-specific schema classes or field meanings beyond small reusable display heuristics.
- Machine-readable formats remain the source of truth for exact structure.
- Fallback behavior should remain stable and deterministic when the renderer cannot produce a better summary.

## Output Semantics

After this change, output mode semantics are:

- `table`: readable terminal summary view
- `json`: normalized machine-readable structure
- `yaml`: normalized machine-readable structure
- `raw-json`: raw provider response
- `raw-yaml`: raw provider response

This means `table` mode is allowed to show the same data with a different textual shape than `json` or `yaml` as long as it remains faithful to the meaning of the value.

## Renderer Design

The change should stay localized to `src/atlassian_cli/output/renderers.py`.

The existing row extraction and column union logic should remain in place. The only behavioral change is how each cell value is converted to display text before being added to the Rich table.

Helper structure:

- `_format_table_cell(value)`: dispatch by value type
- `_summarize_mapping(value)`: summarize dictionaries
- `_summarize_sequence(value)`: summarize lists and other sequences
- `_compact_scalar(value)`: normalize scalar display values and flatten multiline text
- `_fallback_json(value)`: stable compact fallback for complex values

This keeps the responsibilities separate:

- row extraction decides what becomes a row
- column discovery decides which columns exist
- cell formatting decides how a value should look in a terminal

## Cell Summarization Rules

### Scalars

- `None` becomes an empty string.
- strings remain strings, but embedded newlines should be collapsed to spaces.
- booleans and numbers should keep their natural string form.

### Dictionaries

For dictionaries, the renderer should prefer concise display fields over raw structure output.

The summary priority should favor common human-readable keys such as:

- `display_name`
- `name`
- `title`
- `key`
- `id`

When useful, the renderer may combine a primary label with one secondary field instead of showing only one value. Preferred combinations include:

- `display_name` plus `email` rendered as `Display Name <email@example.com>`
- `key` plus `name` rendered as `KEY (Name)`

If none of the preferred summary fields exist, the renderer should fall back to compact JSON rather than Python `repr`.

### String Lists

Lists of simple scalar values should render as comma-separated text.

Example:

- `["prod", "sev1", "backend"]` becomes `prod, sev1, backend`

### Lists Of Objects

Lists of mappings should summarize each element with the same dictionary rules, then join the results with commas.

Example:

- `[{"display_name": "Alice"}, {"display_name": "Bob"}]` becomes `Alice, Bob`

This keeps list-heavy fields readable without expanding them into more columns.

### Complex Nested Values

If a value cannot be summarized reliably by the rules above, the renderer should use compact JSON as a deterministic fallback.

The fallback should be:

- single-line
- compact
- key-sorted for stable output
- JSON-shaped rather than Python-shaped

This avoids braces with single quotes and other Python-specific formatting noise.

## Compatibility Boundary

The compatibility boundary should be explicit:

- top-level normalized data passed into the renderer stays unchanged
- row extraction stays unchanged
- column order and sparse-column union behavior stay unchanged
- only the textual representation of table cells changes

This allows the CLI to improve terminal readability without changing API-facing contracts for `json` or `yaml`.

## Scope

This design applies to all current resources that flow through the generic renderer, including Jira, Confluence, and Bitbucket models.

It is intentionally generic rather than resource-specific. The implementation should not add product-specific formatting branches such as Jira-only status logic or Bitbucket-only reviewer logic.

## Testing

Add or update renderer tests in `tests/output/test_renderers.py`.

Coverage should include:

- dictionaries with `name` summarize to the value instead of raw braces
- user-like dictionaries with `display_name` and `email` summarize to a readable combined label
- string lists render as comma-separated text
- lists of dictionaries render as comma-separated summaries
- multiline strings are flattened into a single line
- complex values without preferred summary keys fall back to compact JSON
- empty list input still returns an empty string
- column order and sparse-column union behavior remain intact

Tests should assert semantic readability outcomes rather than Rich border details.

## Acceptance Criteria

- common fields such as `status`, `assignee`, `labels`, and reviewer lists no longer display raw Python `repr` in normal table output
- the table output is easier to scan in a 120-column terminal for representative Jira, Confluence, and Bitbucket payloads
- `json`, `yaml`, `raw-json`, and `raw-yaml` outputs remain unchanged
- existing table renderer behavior around row extraction, empty collections, and sparse columns remains covered by tests
