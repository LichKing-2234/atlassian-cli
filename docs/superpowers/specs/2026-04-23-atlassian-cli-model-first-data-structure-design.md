# Atlassian CLI Model-First Data Structure Design

## Summary

Redesign the CLI's Bitbucket, Confluence, and Jira data structures so the default normalized output is driven by CLI-owned resource models rather than thin service-layer dictionary shaping.

The redesign should align the CLI with the core `mcp-atlassian` principle of `from_api_response()` plus `to_simplified_dict()` without turning this repository into a full `mcp-atlassian` port. The first phase covers all three products together, keeps the current command surface and raw output modes, and allows default normalized output shapes to change.

## Goals

- Replace thin DTO-style schemas with real CLI-owned resource models.
- Make normalized `json`, `yaml`, and `table` output flow through model parsing and model serialization.
- Align default resource shapes more closely with `mcp-atlassian`.
- Make the model layer aware of Cloud, Server, and Data Center response differences.
- Keep execution limited to Server and Data Center in phase 1.
- Preserve `raw-json` and `raw-yaml` as direct provider response views.
- Apply the same model-first structure to Bitbucket, Confluence, and Jira in one phase.

## Non-Goals

- Implementing Cloud provider execution support in phase 1.
- Rebuilding the CLI around `mixin` fetchers or the full `mcp-atlassian` package structure.
- Preserving the exact current normalized JSON and YAML output shapes.
- Adding major new command resources beyond the current CLI surface.
- Mirroring every `mcp-atlassian` field or helper if the current CLI does not need it.

## Phase Boundary

Phase 1 intentionally changes the default normalized output contract.

What stays stable:

- command names
- command arguments
- provider raw responses
- `raw-json`
- `raw-yaml`
- Server and Data Center execution behavior

What may change:

- default `json` output shapes
- default `yaml` output shapes
- top-level list and search envelopes
- table column composition

Cloud remains unsupported at execution time, but the model layer should be able to parse representative Cloud-style payloads for the resources already exposed by the current command set so later Cloud provider work does not require another schema redesign.

## Design Principles

- Stable output contracts should belong to CLI-owned models, not service-layer field copies.
- Providers should return raw SDK payloads and should not own output shaping.
- Services should coordinate resource operations and raw-versus-normalized branching, not parse deeply nested payloads field by field.
- Models should absorb deployment-specific response differences and missing-field variation.
- Missing optional fields should degrade to omission or safe defaults rather than raising validation errors.
- Search and list results should expose explicit envelopes instead of bare lists whenever the command semantics include paging or collection metadata.

## Current Problems

The current code has the right high-level layering but the wrong data-structure boundary.

- Product `schemas.py` files define thin `BaseModel` classes with little or no parsing behavior.
- Services perform direct payload extraction and dictionary shaping.
- Provider Protocols describe only a fraction of the methods services actually rely on.
- The normalized output contract is fragile because optional nested fields can trigger validation errors.
- Search and list commands usually collapse into bare lists and drop pagination metadata.
- Table rendering currently depends on the first row's keys, so sparse list output can silently lose columns.
- Bitbucket pull request normalization is especially brittle and the merge write path is structurally broken.

## Target Architecture

The target runtime flow becomes:

`command -> service -> provider -> raw SDK payload -> ApiModel.from_api_response() -> to_simplified_dict() -> renderer`

### Provider layer

Providers continue to:

- select the correct SDK calls for the active product and deployment
- return raw `atlassian-python-api` payloads
- remain the only layer that knows concrete SDK method names

Providers should not:

- trim fields for display
- convert raw payloads into normalized dictionaries
- own resource contract decisions

### Service layer

Services become resource orchestrators.

They should:

- select the appropriate resource model or result envelope
- expose normalized and raw methods
- handle resource-level write semantics and command-oriented branching

They should not:

- manually build most nested normalized dictionaries
- encode backend-specific field paths beyond what is needed to choose the right model

### Model layer

The model layer becomes the normalization boundary.

Each resource model should own:

- `from_api_response()` for parsing raw payloads
- `to_simplified_dict()` for normalized output
- safe handling of missing fields
- light deployment-aware branching where Cloud and Server/DC payloads differ

The local codebase does not need the full `mcp-atlassian` hierarchy. It should borrow the core pattern, not the full breadth.

### Render layer

The renderer remains generic.

It should:

- serialize dictionaries and lists
- remain unaware of product-specific schema logic
- stop depending on the first row only for table columns

It should not:

- implement resource-specific trimming logic
- re-interpret raw payloads

## File Structure Changes

Introduce a shared model base layer:

- Create `src/atlassian_cli/models/base.py`
- Create `src/atlassian_cli/models/common.py`

Keep the existing product file layout, but upgrade `schemas.py` from thin DTOs to real parsing and serialization models:

- `src/atlassian_cli/products/jira/schemas.py`
- `src/atlassian_cli/products/confluence/schemas.py`
- `src/atlassian_cli/products/bitbucket/schemas.py`

Update services so they delegate shaping to models:

- `src/atlassian_cli/products/jira/services/*.py`
- `src/atlassian_cli/products/confluence/services/*.py`
- `src/atlassian_cli/products/bitbucket/services/*.py`

Expand provider contracts so the interface matches actual usage:

- `src/atlassian_cli/products/jira/providers/base.py`
- `src/atlassian_cli/products/confluence/providers/base.py`
- `src/atlassian_cli/products/bitbucket/providers/base.py`

Update output rendering for sparse model output:

- `src/atlassian_cli/output/renderers.py`

## Shared Model Design

Introduce an `ApiModel` base class with two required behaviors:

- `from_api_response(data, **kwargs)`
- `to_simplified_dict()`

The shared base may also provide:

- timestamp formatting helpers
- optional omit-empty helpers
- lightweight normalization helpers for IDs and strings

This base should stay small. Product-specific parsing rules belong in product models.

## Jira Model Design

### Core resource models

- `JiraIssue`
- `JiraProject`
- `JiraUser`
- `JiraSearchResult`

### Supporting models

- `JiraUserRef`
- `JiraStatus`
- `JiraPriority`
- `JiraIssueType`
- small nested models for comments, attachments, and parent references where those fields are emitted by the normalized contract

### Parsing rules

The Jira models should be aware of:

- Cloud ADF versus Server/DC plain string content
- Cloud user identifiers such as `accountId`
- Server/DC user identifiers such as `name` and `key`
- optional nested fields like `resolution`, `parent`, `subtasks`, and `attachment`
- search result envelopes including `total`, `startAt`, and `maxResults`

### Default normalized shapes

`jira issue get` should return a resource object rather than the current thin summary. The normalized object should include the current essentials plus richer resource fields such as:

- `id`
- `key`
- `summary`
- `description`
- `status`
- `issue_type`
- `priority`
- `assignee`
- `reporter`
- `created`
- `updated`
- `labels`
- `project`
- `resolution`
- `duedate`
- `resolutiondate`
- `parent`
- `subtasks`
- `comments`
- `attachments`
- `url`

`jira issue search` should return an envelope:

- `total`
- `start_at`
- `max_results`
- `issues`

`jira project get` and `jira project list` should move beyond `key`, `name`, and `project_type` to support richer project resource output.

`jira user get` and `jira user search` should normalize to a Cloud-aware and Server-aware user shape that can carry `display_name`, `name`, `key`, `account_id`, `email`, and `avatar_url` when available.

## Confluence Model Design

### Core resource models

- `ConfluencePage`
- `ConfluenceSpace`
- `ConfluenceAttachment`
- collection envelope models for list commands

### Supporting models

- `ConfluenceUserRef`
- `ConfluenceVersion`

### Parsing rules

The Confluence models should be aware of:

- Cloud versus Server/DC URL formats
- `_expandable.space` fallbacks
- attachment payload variations
- body format differences and optional content inclusion
- write responses that may omit detail fields compared with `get_page_by_id`

### Default normalized shapes

`confluence page get`, `create`, and `update` should normalize to a page resource that can include:

- `id`
- `title`
- `type`
- `status`
- `space`
- `version`
- `author`
- `created`
- `updated`
- `url`

The model should support `content`, but phase 1 should not force full page body into default normalized output unless the command semantics require it.

`confluence space get` and `list` should normalize to:

- `id`
- `key`
- `name`
- `type`
- `status`

`confluence attachment list` and `upload` should normalize to:

- `id`
- `title`
- `media_type`
- `file_size`
- `download_url`
- `version_number`
- `created`
- `author_display_name`

All normalized Confluence collection commands should return an envelope with `results`. They should also include `start_at` and `max_results` when the underlying provider call is paged, and they may omit only collection metadata that the backend does not supply.

## Bitbucket Model Design

### Core resource models

- `BitbucketProject`
- `BitbucketRepo`
- `BitbucketBranch`
- `BitbucketPullRequest`
- collection envelope models for list commands

### Supporting models

- `BitbucketUserRef`
- `BitbucketReviewer`
- `BitbucketRef`

### Parsing rules

The Bitbucket models should be aware of:

- nested author and reviewer payload variation
- optional pull request participant data
- missing `fromRef` or `toRef` details
- repository and project metadata differences between minimal list payloads and detailed get payloads
- write operation responses that may not contain the same fields as read responses

### Default normalized shapes

`bitbucket project get` and `list` should support a richer project resource, including fields such as `id`, `key`, `name`, `description`, and `public` when available.

`bitbucket repo get`, `list`, and `create` should support a richer repo resource with fields such as:

- `slug`
- `name`
- `project`
- `state`
- `public`
- `archived`
- `forkable`
- `default_branch`
- `links`

`bitbucket branch list` should return an envelope with `results`, where each branch object can carry:

- `id`
- `display_id`
- `latest_commit`
- `is_default`

`bitbucket pr get`, `list`, `create`, and `merge` should move to a real pull request resource object with fields such as:

- `id`
- `title`
- `description`
- `state`
- `open`
- `closed`
- `author`
- `reviewers`
- `participants`
- `from_ref`
- `to_ref`
- `created_date`
- `updated_date`
- `links`

This is the highest-risk resource in the current code and should be treated as a primary regression target.

## Provider Contract Design

Phase 1 should upgrade provider Protocols so they describe the full method surface actually consumed by services.

These Protocols should:

- include all currently used read and write methods
- use keyword signatures that match the local provider wrappers
- serve as the typing boundary between services and providers

They should not attempt to encode model serialization behavior. Providers still return raw payloads.

## Output Contract Rules

The normalized output rules become:

- single-resource commands return a resource object
- search commands return a result envelope
- list commands return a result envelope; include collection metadata fields when the provider exposes them
- raw modes return the original provider response unchanged

This means normalized collection output becomes more explicit and less ambiguous than the current `list[dict]` style.

## Error Handling Rules

Model parsing should favor resilience.

Required rules:

- missing optional nested objects must not cause validation failure
- IDs should normalize to strings where the backend may return numbers or strings
- unknown or unavailable optional fields should be omitted from simplified output unless a safe default is part of the contract
- services should still surface hard provider and transport failures normally

The model layer should protect against shape drift, not hide real request failures.

## Migration Strategy

Phase 1 should be implemented in controlled steps:

1. Introduce shared model base types and helpers.
2. Upgrade Jira schemas and services to model-first output.
3. Upgrade Confluence schemas and services to model-first output.
4. Upgrade Bitbucket schemas and services to model-first output.
5. Expand provider Protocols to match actual usage.
6. Update the renderer to handle sparse top-level fields safely.
7. Update command and service tests for the new normalized contracts.

This order keeps the command surface stable while moving the output contract boundary product by product.

## Testing Strategy

Phase 1 requires more than happy-path command tests.

### Model tests

Add or expand tests for:

- `from_api_response()`
- `to_simplified_dict()`
- missing field handling
- Cloud-style payload parsing
- Server/DC-style payload parsing

### Service tests

Add or expand tests for:

- raw versus normalized branching
- result envelope behavior
- write-operation normalized payloads

### Renderer tests

Add tests to ensure:

- sparse list output does not lose columns because later rows introduce additional keys
- nested simplified payloads still serialize predictably

### Regression tests

Explicitly cover current structural defects:

- Bitbucket pull request normalization with missing author or ref fields
- Bitbucket pull request merge parameter handling
- list and search output no longer collapsing important collection metadata

### Smoke coverage

Keep the existing minimal real-instance smoke coverage for Jira, Confluence, and Bitbucket and expand it where a resource contract changes substantially so model parsing is validated against real SDK responses.

## Documentation Impact

Update user-facing docs after implementation to reflect that normalized output now represents richer resource objects and collection envelopes.

This should include:

- README examples
- command help expectations where needed
- any docs that currently imply normalized output is a thin summary projection

## Success Criteria

Phase 1 is complete when all of the following are true:

- all existing commands still execute for Server and Data Center
- `raw-json` and `raw-yaml` still expose raw provider payloads
- default normalized output for Jira, Confluence, and Bitbucket is model-driven
- collection commands use explicit envelopes instead of bare normalized lists
- provider, service, and model responsibilities are clearly separated in code
- current Bitbucket pull request structural failures are fixed
- the model layer can parse representative Cloud-style payloads without requiring Cloud execution support
