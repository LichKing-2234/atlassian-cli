# Atlassian CLI Attachment Commands Design

## Context

GitHub issue #28 requests first-class Jira and Confluence attachment operations.
The current repository already has `confluence attachment list/upload/download`
commands with live e2e coverage, but Jira attachments are only exposed as
metadata inside issue reads and as an indirect `--attachments` update option.

The design follows the command shape approved in brainstorming option B:

- add nested Jira issue attachment commands;
- add nested Confluence page attachment commands;
- keep the existing top-level Confluence attachment commands as compatibility
  entry points.

The reference behavior comes from `mcp-atlassian` attachment tools, adapted for a
local CLI. The MCP server returns embedded resources and enforces an inline
payload limit; this CLI writes files to disk, so downloads should stream through
the authenticated HTTP session instead of materializing base64 payloads.

## Goals

- Support `jira issue attachment list/upload/download`.
- Support `confluence page attachment list/upload/download`.
- Preserve existing `confluence attachment list/upload/download` behavior.
- Normalize attachment metadata for user-facing output while preserving
  `raw-json` for API payload inspection.
- Update help, README examples, unit tests, live e2e coverage, and coverage
  manifest entries for the new command surfaces.

## Non-Goals

- Do not add Jira or Confluence attachment deletion in this phase.
- Do not add batch upload or batch download commands in this phase.
- Do not add MCP-style base64 embedded resources.
- Do not impose a 50 MB inline-resource limit on CLI downloads.
- Do not add Cloud support; the current v1 provider factory remains Server/DC
  only.

## Command Surface

New Jira commands:

```bash
atlassian jira issue attachment list DEMO-1
atlassian jira issue attachment upload DEMO-1 ./report.pdf
atlassian jira issue attachment download DEMO-1 --name report.pdf --destination ./report.pdf
```

New Confluence page commands:

```bash
atlassian confluence page attachment list 1234
atlassian confluence page attachment upload 1234 ./diagram.png
atlassian confluence page attachment download 1234 --name diagram.png --destination ./diagram.png
```

Existing compatibility commands remain valid:

```bash
atlassian confluence attachment list 1234
atlassian confluence attachment upload 1234 --file ./diagram.png
atlassian confluence attachment download 55 --destination ./diagram.png
```

The design intentionally uses `--destination` for file output paths. The CLI
already uses `--output` for render mode selection, so overloading `--output` as a
download path would make command behavior ambiguous.

## Architecture

### Jira Attachments

Add a small Jira attachment layer:

- `src/atlassian_cli/products/jira/schemas.py`
  - add `JiraAttachment`;
  - parse `id`, `filename`, `size`, `mime_type`, `created`, `author`, and
    `download_url`;
  - reuse existing Jira user normalization for author fields.
- `src/atlassian_cli/products/jira/providers/base.py`
  - add protocol methods:
    `list_issue_attachments`, `upload_issue_attachment`, and
    `download_issue_attachment`.
- `src/atlassian_cli/products/jira/providers/server.py`
  - list with `client.issue(issue_key, fields="attachment")`;
  - upload with `client.add_attachment(issue_key, filename)`;
  - download by resolving attachment metadata from the issue and streaming
    `download_url` through `client._session`.
- `src/atlassian_cli/products/jira/services/attachment.py`
  - normalize list and upload output;
  - expose raw list/upload payloads for `raw-json`;
  - resolve `--name` for downloads and return a structured download result.
- `src/atlassian_cli/products/jira/commands/attachment.py`
  - provide the nested command app.
- `src/atlassian_cli/cli.py`
  - register the attachment app under `jira issue attachment`.

### Confluence Attachments

Reuse and extend the existing Confluence attachment layer:

- `src/atlassian_cli/products/confluence/services/attachment.py`
  - support list options `start`, `limit`, `filename`, and `media_type`;
  - support upload `comment`;
  - add download by content id plus attachment name for the new page-scoped
    command surface.
- `src/atlassian_cli/products/confluence/providers/base.py`
  - add optional arguments to `list_attachments` and `upload_attachment`;
  - add a provider method that can download an attachment selected from a page by
    name.
- `src/atlassian_cli/products/confluence/providers/server.py`
  - pass `start`, `limit`, `filename`, and `media_type` to
    `get_attachments_from_content`;
  - pass upload comments to `attach_file`;
  - keep the current attachment-id download implementation for compatibility.
- `src/atlassian_cli/products/confluence/commands/page.py`
  - register a nested `attachment` sub-app that calls the shared service.
- `src/atlassian_cli/products/confluence/commands/attachment.py`
  - keep existing command names and add any shared options that do not change
    behavior.

The existing `confluence attachment download <ATTACHMENT_ID>` command continues
to download by attachment id. The new
`confluence page attachment download <PAGE_ID> --name <FILE>` command downloads
by page and filename.

## Data Flow

List flow:

1. Command parses the container id and optional filters.
2. Service calls provider list method.
3. Provider fetches attachment metadata from Jira or Confluence.
4. Service maps API objects to simplified attachment dictionaries.
5. Renderer prints markdown, JSON, or raw JSON.

Upload flow:

1. Command accepts a local path as a positional argument on new nested commands.
2. Service validates that the path is present and delegates to provider.
3. Provider uses the product client upload method with the authenticated session.
4. Service normalizes the returned attachment metadata and includes the container
   id in the result where available.

Download flow:

1. New nested command accepts a container id, `--name`, and `--destination`.
2. Service lists attachments for the container and finds an exact filename match.
3. If one match exists, provider streams bytes to the destination path.
4. If the destination is a directory, the provider writes the original filename
   inside that directory.
5. Result includes container id, attachment id, filename, path, and bytes written.

## Error Handling

- Missing upload files raise a CLI-facing parameter or runtime error before
  making an API call.
- Missing `--name` matches report that no matching attachment exists for the
  target issue or page.
- Multiple exact filename matches report an ambiguity and require the user to use
  the compatibility attachment-id download path where available.
- Missing download URLs report a clear error with the attachment id or filename.
- Download writes create parent directories as needed, but paths are resolved
  safely so attachment filenames cannot escape the requested destination
  directory.
- Product API errors continue through the existing Typer exception handling path.

## Testing

Unit coverage:

- Jira attachment schema normalization.
- Jira provider list/upload/download with fake client/session objects.
- Jira attachment service list/upload/download name resolution.
- Jira command output and option parsing.
- Confluence service/provider option forwarding for pagination, filename,
  media type, upload comment, and page-scoped download by name.
- Confluence nested page attachment command aliases.

Live e2e coverage:

- Add `jira issue attachment list`, `jira issue attachment upload`, and
  `jira issue attachment download` to `tests/e2e/coverage_manifest.py`.
- Add `confluence page attachment list`, `confluence page attachment upload`, and
  `confluence page attachment download` to the manifest.
- Extend Jira live round trip with a small generated text attachment, list it,
  download it, assert content, and delete the issue in cleanup.
- Extend Confluence live attachment test to exercise both the existing top-level
  commands and the new page-scoped aliases.

Repository verification after implementation:

```bash
ruff format --check .
python -m pytest -q
ruff check README.md pyproject.toml src tests docs
ATLASSIAN_E2E=1 python -m pytest tests/e2e/test_jira_live.py::test_jira_issue_round_trip_live -q
ATLASSIAN_E2E=1 python -m pytest tests/e2e/test_confluence_live.py::test_confluence_attachment_round_trip_live -q
```

If live credentials or environment are unavailable, the implementation cannot be
called live-verified.

## Documentation

Update README command examples and feature bullets to include the nested Jira and
Confluence page attachment commands. Keep all public examples on the approved
placeholder set, including `DEMO-1`, `1234`, `report.pdf`, and `diagram.png`.

Help text should mention:

- downloads use `--destination` for file paths;
- `raw-json` returns provider/API payloads;
- Confluence top-level attachment commands remain compatible entry points;
- delete and batch operations are not part of this phase.

## Acceptance Criteria

- `atlassian jira issue attachment list DEMO-1 --output json` returns normalized
  attachment metadata.
- `atlassian jira issue attachment upload DEMO-1 ./report.pdf --output json`
  uploads one file and returns normalized metadata.
- `atlassian jira issue attachment download DEMO-1 --name report.pdf
  --destination ./report.pdf --output json` writes the file and reports the path.
- `atlassian confluence page attachment list 1234 --output json` returns the
  same normalized metadata shape as the existing Confluence attachment list.
- `atlassian confluence page attachment upload 1234 ./diagram.png --output json`
  uploads one file through the shared Confluence attachment service.
- `atlassian confluence page attachment download 1234 --name diagram.png
  --destination ./diagram.png --output json` writes the file and reports the
  path.
- Existing `atlassian confluence attachment ...` commands remain covered and
  working.
- README, help tests, unit tests, live e2e manifest, and affected live e2e paths
  are updated with public-safe examples.
