# Atlassian CLI Default Toolset Semantic Alignment Design

## Summary

Redesign the CLI's default Jira and Confluence command behavior so it aligns with `mcp-atlassian` `TOOLSETS=default` at the level of input semantics, execution semantics, and default normalized output, not just command presence.

This phase intentionally allows breaking changes in default `json` and `yaml` output and does not treat backward compatibility for existing CLI flags as a primary goal. `raw-json` and `raw-yaml` remain stable as direct provider-response views.

The same phase also hardens the live e2e suite so it adapts to real instance constraints instead of assuming idealized Jira, Confluence, and Bitbucket seed data.

## Goals

- Make the CLI's default Jira and Confluence commands materially closer to `mcp-atlassian` `TOOLSETS=default`.
- Align command inputs with MCP semantics where the current CLI is too narrow to express real workflows.
- Align default normalized output with MCP-style resource objects and collection envelopes.
- Preserve raw output modes as direct provider payload views.
- Improve live e2e reliability by discovering environment constraints instead of hardcoding optimistic assumptions.
- Keep the existing high-level layering: `command -> service -> provider -> schema/model`.

## Non-Goals

- Implement Cloud execution support in CLI v1.
- Achieve literal one-to-one API parity with every MCP tool option when the underlying deployment boundary differs.
- Rebuild the CLI around a new MCP compatibility layer or embed `mcp-atlassian` directly.
- Refactor non-default toolsets as part of the main semantic alignment scope.
- Preserve existing normalized `json` or `yaml` shapes.

## Scope Boundary

This work targets only the six `mcp-atlassian` default toolsets:

- `jira_issues`
- `jira_fields`
- `jira_comments`
- `jira_transitions`
- `confluence_pages`
- `confluence_comments`

The following command groups are out of primary scope and should only change if shared infrastructure requires it:

- Jira `project` and `user`
- Confluence `space` and `attachment`
- All Bitbucket command groups

Bitbucket live e2e stability may still receive targeted test-support changes because the repository's live suite currently covers the full CLI surface.

## Current Problems

The CLI already exposes command names that roughly match the default MCP toolsets, but several commands are still not semantically equivalent:

- Jira create and update operations cannot express the richer field payloads needed by real projects.
- Confluence page search, get, create, and update still expose a narrower parameter model than MCP.
- Default normalized output is still CLI-specific in important places, especially for Jira issue and Confluence page resources.
- The live e2e suite assumes happy-path project and repository configuration that does not hold on many real instances.

The result is a misleading form of alignment: users can discover commands with similar names, but cannot consistently reproduce the same workflows or expect a similar resource shape.

## Design Principles

- Align semantics first, names second.
- Keep command modules thin.
- Keep provider modules close to SDK and HTTP behavior.
- Put user-visible workflow logic and environment adaptation in services.
- Keep normalized output owned by CLI models, not ad hoc service dictionaries.
- Do not silently invent business data to satisfy instance-specific required fields.
- Prefer explicit user input or explicit test configuration over hidden guesswork.

## Target Architecture

### Command Layer

Command modules should expose CLI parameters that are much closer to MCP tool semantics than the current CLI parameters.

They should:

- accept richer option sets for Jira issue and Confluence page operations
- parse user-facing string inputs into structured service inputs
- remain responsible for CLI ergonomics only

They should not:

- perform environment discovery
- synthesize normalized output
- encode deployment-specific business logic

### Service Layer

Services become the semantic alignment boundary.

They should:

- translate MCP-like CLI inputs into provider calls
- perform instance discovery where it materially improves user outcomes
- normalize collection envelopes and resource response structure
- provide better validation errors for missing required fields and invalid option values

This is also the right layer for live-instance adaptation such as Jira create metadata inspection and Confluence search-mode selection.

### Provider Layer

Providers continue to wrap `atlassian-python-api` and any small direct HTTP glue needed when the SDK does not fully expose a needed operation.

They should:

- accept explicit typed inputs from services
- return raw product payloads
- avoid owning output contracts

They should not:

- emit CLI-normalized dictionaries
- decide how to infer required business values

### Model And Schema Layer

Default normalized `json` and `yaml` output should move closer to MCP-style resources and envelopes.

This layer should:

- parse raw provider payloads into richer resource models
- emit simplified dictionaries that are closer to MCP output conventions
- support omission of absent optional fields without validation failure
- distinguish raw output from normalized output cleanly

## Command Semantics

### Jira Issues

#### `jira issue get`

Replace the narrow current read interface with MCP-like read controls:

- positional `issue_key`
- `--fields`
- `--expand`
- `--comment-limit`
- `--properties`
- `--update-history`

Default normalized output should be a richer issue resource instead of the current thin shape.

#### `jira issue search`

Support:

- `--jql`
- `--fields`
- `--limit`
- `--start-at`
- `--projects-filter`
- `--expand`

Server and Data Center support should stay explicit. Cloud-only pagination tokens are out of scope for execution support.

Default normalized output should remain a collection envelope and move closer to MCP pagination semantics.

#### `jira issue create`

Replace the current fixed-field create path with a richer MCP-like interface:

- `--project-key`
- `--summary`
- `--issue-type`
- `--assignee`
- `--description`
- `--components`
- `--additional-fields`

`--additional-fields` is required for practical parity because real instances often require custom fields, parent links, Epic links, versions, or other project-specific values.

Default normalized output should move toward a `message + issue` structure.

#### `jira issue update`

Replace the current `summary` and `description` only interface with:

- positional `issue_key`
- `--fields`
- `--additional-fields`
- `--components`
- `--attachments`

`--fields` should be the main structured update entrypoint. `--additional-fields` remains available for more complex or custom updates.

Default normalized output should move toward a `message + issue` structure rather than a small success dictionary.

#### `jira issue batch-create`

Align toward MCP semantics:

- `--issues`
- `--validate-only`

For CLI usability, `--issues` may accept either an inline JSON array or an `@path/to/file.json` indirection convention while still representing a single structured input parameter.

#### `jira issue changelog-batch`

Keep the command but make the guard message explicitly reflect the true boundary:

- available only on Jira Cloud
- intentionally unsupported for Server and Data Center execution in v1

The command should not present itself as a generic future placeholder.

### Jira Fields, Comments, And Transitions

These groups are already close on command presence. The main work is:

- tighten normalized output shapes
- align parameter names where needed
- keep response envelopes consistent with the rest of the default Jira surface

### Confluence Pages

#### `confluence page search`

Support:

- `--query`
- `--limit`
- `--spaces-filter`

Search must distinguish simple user text from explicit CQL instead of always rewriting to one fixed query pattern.

#### `confluence page get`

Support:

- positional `page_id`, or `--title` plus `--space-key`
- `--include-metadata`
- `--convert-to-markdown`

Default normalized output should be allowed to return content and metadata using an MCP-like structure instead of the current simplified page object only.

#### `confluence page history`

Support:

- positional `page_id`
- `--version`
- `--convert-to-markdown`

Default normalized output should preserve useful version content semantics instead of collapsing back to a metadata-only resource shape.

#### `confluence page create`

Support:

- `--space-key`
- `--title`
- `--content`
- `--parent-id`
- `--content-format`
- `--enable-heading-anchors`
- `--include-content`
- `--emoji`

Default normalized output should move toward `message + page`.

#### `confluence page update`

Support:

- positional `page_id`
- `--title`
- `--content`
- `--is-minor-edit`
- `--version-comment`
- `--parent-id`
- `--content-format`
- `--enable-heading-anchors`
- `--include-content`
- `--emoji`

#### `confluence page diff`, `move`, `children`, and `tree`

These commands already cover the core workflows. Work here is mainly about consistent output shape and argument naming.

### Confluence Comments

Keep `list`, `add`, and `reply`, but align the normalized resource shape with MCP-style comment objects and collection envelopes.

## Output Contract Changes

This phase intentionally allows breaking changes in normalized output.

### Stable Modes

These remain stable:

- `raw-json`
- `raw-yaml`

They should continue to expose provider payloads directly.

### Changing Modes

These may change significantly:

- `json`
- `yaml`
- any default table rendering that depends on the normalized dictionary shape

### Normalized Shape Direction

The normalized output should move toward:

- richer resource objects
- more consistent collection envelopes
- top-level `message + resource` structures for write operations where MCP uses them

The exact goal is not literal byte-for-byte matching. The goal is that users familiar with MCP should recognize the same resource concepts and envelope patterns in the CLI.

## Instance Adaptation

### Production CLI Adaptation

The CLI should adapt where the behavior is user-beneficial and deterministic.

#### Jira

Before create or structured update flows, the service layer should be able to inspect issue metadata and:

- detect missing required fields
- validate issue type and allowed values
- produce explicit error messages describing what additional input is required

The CLI should not silently guess business-specific values for required fields that cannot be safely inferred.

#### Confluence

The service layer should:

- distinguish plain text search from explicit CQL
- make content-format behavior explicit
- make content-versus-metadata read behavior explicit

### Test-Only Adaptation

The e2e suite should contain additional helpers for instance discovery, but those helpers must stay in `tests/e2e/support/` and must not leak into production behavior.

Examples:

- finding a usable Jira issue type and a minimal valid payload for the configured project
- discovering whether a configured Confluence space is writable and whether page creation must happen under a known parent page
- avoiding dependence on a hardcoded Bitbucket repository that may not exist on a real instance

## Live E2E Design

### Jira Live E2E

Jira live tests should stop assuming that `Task + summary + description` is enough to create an issue.

Instead, test support should:

- inspect available issue types
- inspect required fields for the selected issue type
- fill only values that can be deterministically derived, such as a first allowed option when the field semantics are generic enough for test use
- use explicit environment variables when required fields cannot be safely inferred
- skip with a precise reason when the instance requires business data the tests do not know

### Confluence Live E2E

Confluence live tests should stop assuming the default configured space is writable at the root.

The suite should support configuration such as:

- a writable space key
- an optional writable parent page ID

When required writeability is absent, tests should skip precisely rather than fail with generic create errors.

### Bitbucket Live E2E

Bitbucket is not part of the default toolset alignment goal, but the repository's full live suite still depends on it.

The live suite should:

- stop assuming a single seed repository always exists
- prefer explicit environment configuration
- fall back to discovery or temporary repository creation when the instance policy allows it

## Risks

- Existing users of normalized `json` and `yaml` output may need to update scripts.
- `atlassian-python-api` may not expose every required semantic option directly, which may require small provider-side glue or direct HTTP requests in narrow cases.
- Some real Jira instances may require fields whose valid values are not discoverable in a safe generic way; those cases must remain explicit-user-input problems, not hidden automation.
- Confluence content-format behavior may vary enough across instances that part of the design may require additional provider normalization.

## Success Criteria

This design is successful when all of the following are true:

- default-toolset Jira and Confluence commands can express the same practical workflows that MCP default toolsets expose for Server and Data Center
- default normalized output is recognizably closer to MCP resource and envelope semantics
- the Jira changelog batch gap remains explicit as a Cloud-only boundary instead of being implied as supported
- live e2e results depend primarily on real product constraints, not on outdated hardcoded assumptions in the test suite

## Recommended Implementation Order

1. Align Jira default-toolset command semantics and normalized output.
2. Align Confluence default-toolset command semantics and normalized output.
3. Add shared live e2e discovery helpers and update live modules to use them.
4. Update README, CONTRIBUTING, and command examples to document the new normalized-output contract and live test requirements.
