# Atlassian CLI Confluence Markdown Rendering Design

## Summary

Render Confluence page `content.value` as Markdown in human-readable `--output markdown` mode when the value is Confluence storage HTML.

Keep `json`, `yaml`, `raw-json`, and `raw-yaml` unchanged. Keep service and schema payloads unchanged. Restrict the behavior to the markdown render path for single-resource page detail output.

## Goals

- Make `atlassian confluence page get ... --output markdown` readable when `content.value` contains Confluence storage HTML.
- Make `atlassian confluence page history ... --output markdown` use the same rendering behavior.
- Preserve the current normalized payload shape for machine-readable output.
- Preserve existing behavior for non-HTML content.

## Non-Goals

- Changing `json` or `yaml` payload contents.
- Changing raw output modes.
- Adding a new CLI flag for content rendering.
- Rendering images or rich Confluence macros with browser-level fidelity.
- Rewriting Confluence storage HTML at the provider, schema, or service layer.

## Chosen Approach

Apply HTML-to-Markdown conversion only inside the markdown renderer.

The renderer already decides how normalized payloads become terminal-facing text. This is the narrowest integration point that solves the readability problem without leaking output-mode concerns into services or schemas.

## Scope

This change applies to markdown detail rendering for envelopes shaped like:

```json
{
  "metadata": { "id": "1234", "title": "Example Page" },
  "content": { "value": "<p>...</p>" }
}
```

It also applies when that envelope is nested under a write-result wrapper such as:

```json
{
  "message": "Page updated successfully",
  "page": {
    "metadata": { "id": "1234", "title": "Example Page" },
    "content": { "value": "<p>...</p>" }
  }
}
```

It does not apply to:

- collection output
- diff output
- raw output
- normalized `json` or `yaml`
- non-Confluence resources unless they happen to pass through the exact same markdown detail path and meet the same HTML detection rule

## Rendering Rules

### HTML detection

Treat `content.value` as HTML only when it looks like markup rather than existing Markdown or plain text.

Use a conservative detection rule:

- convert when the string contains HTML tags such as `<p>`, `<br>`, `<a>`, `<table>`, `<ol>`, `<ul>`, `<li>`
- convert when the string contains Confluence storage tags such as `<ac:` or `<ri:`
- otherwise leave the value unchanged

This avoids double-processing existing Markdown such as `## Runbook`.

### Conversion library

Use `markdownify`.

Why `markdownify`:

- it preserved Confluence tables better than the other tested options
- it keeps output in Markdown, which matches the existing renderer contract
- it is good enough for links, lists, emphasis, and basic tables without adding browser-engine complexity

### Conversion behavior

Use a minimal configuration first:

- `heading_style="ATX"`

Do not add custom preprocessing or custom tag handlers in the first implementation unless tests show a concrete gap that blocks readability.

Expected behavior:

- paragraphs become Markdown paragraphs
- links remain links
- ordered and unordered lists remain lists
- tables become Markdown tables when possible
- unsupported Confluence-specific structures degrade to readable text rather than exact visual parity

## Architecture

### Render layer

Add a small helper in the output layer, near the existing markdown renderer, that:

1. checks whether a `content.value` string looks like HTML
2. converts it with `markdownify` when needed
3. returns the original string otherwise

`render_markdown()` should call this helper only when rendering detail-body fields, not for list summaries or preview rows.

### Service and schema layers

No service or schema changes.

`PageService` continues to expose normalized page envelopes with raw `content.value`. `ConfluencePage` continues to store the provider's `body.storage.value` as-is.

## Dependency

Add `markdownify` as a project dependency so the markdown renderer can use it at runtime.

The implementation should not depend on optional local packages or ad hoc shell tools.

## Testing

Add tests that cover:

- storage HTML in page detail output is converted to readable Markdown
- existing Markdown content remains unchanged
- nested page envelopes still render correctly after conversion
- machine-readable output tests remain unchanged because payload contents are not modified before serialization

Representative assertions should verify:

- `## Content` is still present
- HTML tags such as `<p>` and `<ac:structured-macro>` do not appear in rendered markdown output when conversion is expected
- readable Markdown fragments such as list items, links, or table separators do appear

## Risks

- `markdownify` will not faithfully reproduce all Confluence macros.
- some Confluence storage constructs may produce awkward but readable Markdown
- generic HTML detection could affect another detail payload if that payload reuses the same envelope shape and stores literal HTML intentionally

These risks are acceptable for the first step because the alternative today is raw storage HTML in markdown output.

## Success Criteria

- `atlassian confluence page get ... --output markdown` no longer prints raw Confluence storage HTML for page content
- `atlassian confluence page history ... --output markdown` behaves the same way
- `--output json`, `--output yaml`, `--output raw-json`, and `--output raw-yaml` keep their current behavior
