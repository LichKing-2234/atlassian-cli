# Atlassian CLI Richer Markdown Detail Design

Date: 2026-04-30

## Summary

Expand the CLI's default `markdown` detail output so single-resource reads are near-complete instead of summary-like. This applies to direct `get` commands, write-result detail payloads, and interactive collection detail views opened from `list`-style commands.

The design keeps machine-readable output unchanged. It also adds local readability conversion for Confluence page bodies that currently arrive as HTML or storage XHTML so human-readable detail output is usable without raw tag noise.

## Context

The current markdown renderer is intentionally minimal:

- it shows a heading plus a small fixed set of summary fields
- it only treats `description` and `content` as full body sections
- it drops most other normalized fields from detail output
- interactive collection detail uses the same renderer, so the same information loss appears after pressing `Enter` from list views

This is acceptable for shallow summaries, but not for default detail output. Users expect `get` to surface most normalized information without switching to `json` or `yaml`.

Confluence page detail has an additional usability gap. On Server/DC, page content is returned as storage XHTML. The CLI currently passes that content through into markdown detail almost verbatim, which makes many pages unreadable in the default human mode.

## Goals

- Make default markdown detail output near-complete for normalized single-resource payloads.
- Keep one shared detail contract for direct command output and interactive detail views.
- Preserve a stable human-readable shape instead of dumping raw JSON.
- Render Confluence HTML or storage XHTML bodies into readable text for markdown detail output.
- Preserve current machine-readable outputs and current normalized payload contracts as much as possible.

## Non-Goals

- Do not change `json`, `yaml`, `raw-json`, or `raw-yaml` output.
- Do not add server-side Confluence markdown conversion support.
- Do not redesign list summary output or preview output.
- Do not move detail rendering logic into per-product command modules.

## Scope

This change applies to human-readable detail output for:

- direct `get` commands
- detail-style write results such as create/update operations that already render a single resource
- interactive detail opened from collection flows such as `search`, `list`, `children`, or `tree`

This change does not alter collection summary rendering outside the interactive detail view.

## Existing Constraints

- The repository already uses one shared `render_markdown()` entry point for human-readable rendering.
- Interactive collection detail already delegates to the same markdown renderer and should continue to do so.
- Confluence `metadata + content` envelopes are part of the normalized read contract and should remain stable.
- Public docs and tests must use the approved neutral placeholder values.

## Design

### 1. Unified Detail Contract

Single-resource markdown detail output should follow a three-part structure:

1. Heading
2. Core facts block
3. Expanded details block

The heading remains the existing primary identifier plus title format, for example key plus summary or id plus title.

The core facts block shows high-value fields in a stable order when present:

- `state` or `status`
- `issue_type`, `type`, or `priority`
- `assignee`, `author`, or `reporter`
- `project` or `space`
- `from_ref` or `to_ref`
- `version`
- `created`, `updated`, `duedate`, and `resolutiondate`
- `url`

After the core facts block, the renderer expands the remaining normalized fields instead of dropping them.

### 2. Near-Complete Recursive Expansion

The renderer should recursively expand remaining normalized fields using stable markdown rules:

- scalar values render as `- Label: value`
- scalar lists render as bullet lists
- nested objects render as subsections and continue recursively
- lists of objects render as numbered subsections and continue recursively
- long text fields render as full body sections instead of inline bullets

Only empty values are skipped:

- `None`
- empty strings
- empty lists
- empty mappings

No field should disappear simply because it is not in a short allowlist.

### 3. Field Handling Rules

The renderer should classify fields into three groups:

#### Core inline fields

These render near the top in the stable core facts block.

#### Long body fields

These render as dedicated sections with preserved line breaks:

- `description`
- `content`
- `body`
- `diff`
- comment bodies and similar long nested text fields

#### Remaining fields

These render in the expanded details block using recursive rules.

This keeps the first screen useful while still making the full detail nearly complete.

### 4. Stable Ordering

Ordering must be deterministic so repeated reads of the same resource do not jump around visually.

Ordering rules:

- heading first
- core facts in fixed order
- long body fields next in fixed order
- remaining fields in stable source order when possible, otherwise sorted order
- nested object fields follow the same rule set recursively

The renderer should avoid random ordering from plain dictionary iteration when the input order is not trustworthy.

### 5. Confluence Content Readability

For markdown detail output only, the renderer should detect when page content contains HTML or Confluence storage XHTML and convert it into readable text before rendering.

This conversion is local presentation logic, not a service-level contract change.

Readable conversion should preserve practical structure where possible:

- headings
- paragraphs
- line breaks
- ordered and unordered lists
- links as human-readable text
- block quotes
- code blocks
- table cell text

Confluence-specific macro or namespace tags do not need perfect semantic rendering. The priority is readable content extraction. If a construct cannot be faithfully rendered, the renderer should prefer a short readable placeholder or stripped body text over dumping raw tags into the default detail view.

### 6. Interactive Detail Scrolling

Once detail output becomes near-complete, interactive detail must support scrolling.

The interactive browser should keep the current list view behavior but extend detail mode with scroll support:

- `j` and `k` move by line
- `n` and `p` move by page
- `b` or `esc` returns to the list
- `q` quits

The interactive detail view should continue to render the same markdown detail text produced by the shared renderer. Only navigation changes.

## Implementation Shape

Primary implementation should stay in the output layer:

- `src/atlassian_cli/output/markdown.py`
- `src/atlassian_cli/output/interactive.py`

An additional small helper inside the output package may be introduced for content normalization if needed.

Per-product services should remain focused on normalization, not markdown formatting. Confluence service envelopes should remain `metadata + content` so machine output and existing tests stay stable.

## Testing

Add or update tests for:

- expanded single-resource markdown detail output in `tests/output/test_markdown.py`
- nested object and list rendering in markdown detail
- Confluence HTML or storage XHTML readability conversion
- interactive detail scrolling behavior in `tests/output/test_interactive.py`
- stability of Confluence page service envelopes in `tests/products/confluence/test_page_service.py`

The tests should verify that:

- fields that are already normalized do not disappear from markdown detail
- direct `get` and interactive detail share the same detail renderer contract
- Confluence readable detail no longer exposes raw storage XHTML as the default human-readable experience

## Documentation

Update `README.md` to describe the richer default markdown detail behavior and note that Confluence page content is rendered into readable text in markdown mode when possible.

## Risks

- Overly aggressive recursive rendering could become noisy if the renderer does not distinguish core facts from expanded details.
- HTML or XHTML stripping could lose useful structure if conversion is too naive.
- Interactive detail could become hard to use if scrolling is not added alongside richer detail output.

These risks are addressed by the three-part detail layout, explicit body-field handling, and interactive scrolling support.

## Acceptance Criteria

- Default markdown detail output for normalized single-resource payloads is near-complete.
- Information available in normalized objects is visible in markdown detail unless empty or intentionally suppressed for readability.
- Direct `get` output and interactive `Enter` detail use the same rendering contract.
- Confluence page content that arrives as HTML or storage XHTML is readable in default markdown detail output.
- Machine-readable outputs remain unchanged.
