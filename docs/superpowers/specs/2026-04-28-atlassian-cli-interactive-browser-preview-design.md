# Atlassian CLI Interactive Browser Preview Design

## Summary

Refine the interactive collection browser introduced by the markdown-default output redesign so it becomes a practical default terminal browsing experience rather than a minimal proof of concept.

The browser should move from a single long-text list into a compact, high-density list with a live preview panel. The compact list is responsible for fast scanning. The preview panel is responsible for the most useful secondary details. Full detail view remains available on demand.

This design does not change the top-level output contract. `markdown` remains the default human-readable mode, `table` remains removed, and machine-readable modes remain unchanged.

## Relationship To Existing Specs

This design refines the interactive-browser portion of:

- `docs/superpowers/specs/2026-04-28-atlassian-cli-markdown-default-interactive-lists-design.md`

It does not supersede the markdown-default output contract. It narrows and improves the terminal interaction model used by TTY collection commands.

## Goals

- Make the interactive list browser dense enough for real-world browsing.
- Add a live preview pane that updates as selection changes.
- Keep the list single-line and stable even for long titles.
- Preserve full detail view behind `Enter`.
- Improve keyboard efficiency without introducing a heavy multi-panel application.

## Non-Goals

- Reintroducing table output.
- Replacing full detail view with preview-only interaction.
- Building a fully general TUI framework.
- Adding merge, update, delete, or bulk actions inside the browser.
- Adding clipboard integration, multi-select, or remote incremental search.
- Introducing right-side preview as the initial default layout.

## Design Direction

The browser should use a vertically stacked layout:

- top region: compact list
- middle region: live preview for the selected item
- bottom region: status and keybinding hints

The preview should appear below the list, not to the right.

## Why Bottom Preview

Bottom preview is preferred over right-side preview because:

- terminal width is usually more constrained than terminal height
- resource titles are already long and benefit from maximum horizontal room
- a right-side preview would force list titles into harsher truncation
- a bottom preview can show 5 to 10 stable metadata lines without making the list unreadable

## Layout

### Top list region

The list region should display one line per record.

The line should be compact, stable, and width-bounded. It should never expand into multi-line wrapped prose during normal browsing.

For Bitbucket pull requests, the default list line should be:

```text
24990  OPEN  huangpeilin  [FEAT] CSD-77462 add configurable mic test
```

The order of information should be:

- primary identifier
- state or status
- primary person
- title or summary

The list should not include reviewer lists, branch metadata, or long descriptions inline. Those belong in preview.

### Preview region

The preview region should update whenever selection changes.

The preview is a concise summary, not a full detail page. It should answer:

- what is this item
- who owns it
- where is it going
- what secondary context matters before opening full detail

For Bitbucket pull requests, preview should prefer:

- state
- author
- reviewers summary
- from branch
- to branch
- updated timestamp
- short description excerpt

Example shape:

```text
State: OPEN
Author: huangpeilin
Reviewers: Alice, Bob, Carol, +21 more
From: jira/CSD-77462/release/4.5
To: release/4.5
Updated: 2026-04-27 13:19:55

Description:
Add configurable recording device test playback across C++, Android, and Objective-C...
```

### Footer region

The footer should show:

- movement keys
- page keys
- filter key
- refresh key
- detail/open key
- back/quit keys

Example:

```text
j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit
```

## Data Separation

The interactive source should separate three rendering responsibilities:

- `render_item(index, item)`: compact list line only
- `render_preview(item)`: short preview block
- `render_detail(item)`: full markdown detail view

This is important because preview and detail have different density goals.

The current browser implementation effectively treats list and detail as the only two views. That is too coarse. Preview should be a first-class output shape.

## Bitbucket Pull Request Rules

### Compact list line

For `bitbucket pr list`, list lines should include:

- `id`
- `state`
- author display name
- title

Suggested formatting:

```text
24990  OPEN  huangpeilin  [FEAT] CSD-77462 add configurable mic test
```

### Preview content

The preview should include:

- `state`
- `author`
- `reviewers`
- `from_ref`
- `to_ref`
- `updated_date`
- description excerpt

It should not include full raw link payloads, participant payloads, or long nested structures.

### Description preview limit

Preview should show at most a short excerpt of description, not the entire body.

A good first boundary is:

- no more than 3 lines
- each line clipped to the preview width

If description is longer, truncate with an ellipsis rather than wrapping indefinitely.

## Interaction Rules

### Movement and paging

- `j` / `k` and Up / Down move the selected item
- `n` / `p` and PageDown / PageUp move by page-size increments
- selection changes update preview immediately

### Filtering

- `/` enters local filter mode
- filter applies only to already-loaded items
- `Enter` applies the filter
- `Esc` cancels filter editing
- filtered list resets selection to the first visible item

### Refresh

- `r` reloads the first page
- refresh clears transient browser state such as current detail view
- refresh should keep the browser in list mode

### Full detail

- `Enter` from list opens full detail view
- `b` or `Esc` returns to the list
- full detail remains markdown-based rather than switching to raw JSON

## Width And Density Rules

The compact list must be width-bounded.

Rules:

- list entries render on a single logical line
- long lines are truncated with an ellipsis
- list truncation should happen in the browser layer, not by mutating normalized payloads
- preview may use multiple lines, but should still be bounded and clipped

The list should optimize for scan speed. The preview should optimize for selection confidence. Full detail should optimize for completeness.

## Phasing

### Immediate next stage

Implement:

- compact single-line list rows
- bottom preview panel
- live preview updates on selection change
- explicit preview renderer
- description excerpt truncation

### Later stage

Possible later additions:

- right-side preview experiments
- adjustable splitter ratios
- persistent filter indicator styling
- more resource-specific compact list formats

These later items should not block the first usable preview layout.

## Testing

Coverage should include:

- list line formatting produces one compact line per item
- preview text changes when selection changes
- preview excludes long raw nested structures
- long titles in list rows truncate with an ellipsis
- long descriptions in preview truncate with an ellipsis
- entering full detail still works after preview is introduced
- machine-readable outputs remain unaffected

Representative interaction tests should assert browser state and renderer output without requiring brittle full-screen snapshots.

## Acceptance Criteria

- TTY collection browsing no longer relies on a single long-text list alone
- list rows are compact, stable, and single-line
- a preview pane updates as selection changes
- `Enter` still opens full detail and `b`/`Esc` still returns
- long titles and long preview descriptions truncate predictably
- `json`, `yaml`, `raw-json`, and `raw-yaml` behavior remains unchanged
