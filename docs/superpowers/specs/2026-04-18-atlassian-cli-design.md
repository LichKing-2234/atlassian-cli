# Atlassian CLI Design

## Summary

Build a Python CLI for Atlassian Server/Data Center products using `atlassian-python-api` as the underlying client library. The first release supports Jira, Confluence, and Bitbucket Server/DC only, while keeping the internal architecture ready for future Cloud providers.

The CLI should expose stable, resource-oriented commands such as `jira issue get` and `confluence page create` rather than mirroring underlying Python method names. Product- and deployment-specific API differences should be isolated behind provider adapters.

## Goals

- Provide one CLI covering Jira, Confluence, and Bitbucket Server/DC.
- Use a resource-oriented command model with consistent UX across products.
- Support mixed configuration sources: profiles, environment variables, and command-line flags.
- Normalize output, error handling, and pagination behavior across commands.
- Keep the architecture open for future Cloud support without redesigning the command surface.

## Non-Goals

- First-release support for Atlassian Cloud.
- Full one-to-one exposure of every `atlassian-python-api` method.
- Interactive wizard-style workflows.
- Admin-heavy Tier 3 operations in the first release.

## Scope

### Supported products in v1

- Jira Server/Data Center
- Confluence Server/Data Center
- Bitbucket Server/Data Center

### Deployment model

Profiles and internal provider selection must store `deployment` as one of:

- `server`
- `dc`
- `cloud`

The first release only allows execution for `server` and `dc`. `cloud` is reserved for future providers and must produce a clear unsupported error if selected.

## Design Principles

- Stable CLI contracts matter more than exposing raw backend responses.
- Commands should be organized around resources and user tasks, not client implementation details.
- Deployment differences belong in provider implementations, not command handlers.
- The first release should prioritize common workflows and leave lower-frequency administrative features for later tiers.

## Command Model

### Tiering

The CLI command surface is split into three tiers:

1. Tier 1: Common, high-frequency user workflows
2. Tier 2: Useful but more product-specific capabilities
3. Tier 3: Administrative or lower-priority capabilities

The first release implements Tier 1 fully and reserves extension points for Tier 2 and Tier 3.

### Tier 1 resources

#### Jira

- `issue`
- `project`
- `user`

#### Confluence

- `page`
- `space`
- `attachment`

#### Bitbucket

- `project`
- `repo`
- `branch`
- `pr`

### Tier 2 resources

#### Jira

- `board`
- `sprint`

#### Confluence

- `search`

#### Bitbucket

- `hook`
- `branch-permission`

### Tier 3 resources

Tier 3 is reserved for explicit administration and instance-level operations. The architecture should allow these commands to be added later, but they are not implemented in v1.

### Command naming

Commands must be resource-oriented and action-oriented:

- `jira issue get`
- `jira issue search`
- `jira issue create`
- `jira issue update`
- `jira issue transition`
- `confluence page get`
- `confluence page create`
- `bitbucket repo list`
- `bitbucket pr merge`

Command names should stay stable even if the underlying library changes.

## First-Release Functional Scope

### Jira v1

- `jira issue get`
- `jira issue search`
- `jira issue create`
- `jira issue update`
- `jira issue transition`
- `jira project list`
- `jira project get`
- `jira user get`
- `jira user search`

### Confluence v1

- `confluence page get`
- `confluence page create`
- `confluence page update`
- `confluence page delete`
- `confluence space list`
- `confluence space get`
- `confluence attachment list`
- `confluence attachment upload`
- `confluence attachment download`

### Bitbucket v1

- `bitbucket project list`
- `bitbucket project get`
- `bitbucket repo list`
- `bitbucket repo get`
- `bitbucket repo create`
- `bitbucket branch list`
- `bitbucket pr list`
- `bitbucket pr get`
- `bitbucket pr create`
- `bitbucket pr merge`

## Configuration and Authentication

### Configuration sources

The CLI must support three configuration inputs:

1. Profile-based configuration
2. Environment variables
3. Command-line flags

### Precedence

Configuration resolution order:

1. Explicit command-line flags
2. Environment variables
3. Selected `--profile`
4. Default profile

### Profile storage

Default config path:

`~/.config/atlassian-cli/config.toml`

Example profile structure:

```toml
[profiles.prod_jira]
product = "jira"
deployment = "server"
url = "https://jira.example.com"
auth = "basic"

[profiles.wiki]
product = "confluence"
deployment = "dc"
url = "https://confluence.example.com"
auth = "pat"

[profiles.code]
product = "bitbucket"
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"
```

### Authentication model

The CLI should expose a normalized auth model regardless of product-specific terminology.

Supported v1 auth inputs:

- `basic` using `username + password`
- `basic` using `username + token`
- `bearer` using `token`
- `pat` using `token`

Supported v1 command flags:

- `--url`
- `--username`
- `--password`
- `--token`
- `--auth`
- `--profile`

The command layer should not directly care how a specific `atlassian-python-api` client expects its constructor arguments. That translation belongs in provider adapters.

## Architecture

### High-level flow

Every command should follow the same pipeline:

`CLI command -> service -> provider factory -> provider -> atlassian-python-api -> normalized schema -> renderer`

### Responsibilities

- Command handlers parse CLI arguments and invoke services.
- Services implement resource-level operations and business rules.
- Provider factories choose the correct provider for product and deployment.
- Providers translate resource operations into concrete `atlassian-python-api` calls.
- Schemas normalize backend responses into CLI-owned data structures.
- Renderers format normalized data for table, JSON, or YAML output.

### Deployment isolation

Deployment branching must be isolated to provider selection and provider implementation. Command modules must not contain `if deployment == ...` logic.

## Proposed Package Structure

```text
src/atlassian_cli/
  main.py
  cli.py

  core/
    context.py
    errors.py
    exit_codes.py
    pagination.py

  config/
    models.py
    loader.py
    resolver.py

  auth/
    models.py
    resolver.py

  output/
    formatters.py
    renderers.py

  products/
    jira/
      commands/
        issue.py
        project.py
        user.py
        board.py
        sprint.py
      services/
        issue.py
        project.py
        user.py
      providers/
        base.py
        server.py
        cloud.py
      schemas.py

    confluence/
      commands/
        page.py
        space.py
        attachment.py
        search.py
      services/
        page.py
        space.py
      providers/
        base.py
        server.py
        cloud.py
      schemas.py

    bitbucket/
      commands/
        project.py
        repo.py
        branch.py
        pr.py
        hook.py
        branch_permission.py
      services/
        repo.py
        pr.py
      providers/
        base.py
        server.py
        cloud.py
      schemas.py
```

### File boundary rules

- `commands/` modules must not import `atlassian-python-api` directly.
- `services/` modules define resource operations and hide command-specific details.
- `providers/` own backend-specific translation and client construction.
- `schemas.py` defines normalized output shapes owned by the CLI, not copied from raw API responses.

## Provider Design

### Provider decomposition

Providers should be grouped by product and deployment, for example:

- `jira.providers.server`
- `jira.providers.cloud`
- `confluence.providers.server`
- `bitbucket.providers.server`

Each product provider package can implement resource capabilities such as:

- `IssueProvider`
- `ProjectProvider`
- `UserProvider`
- `PageProvider`
- `RepoProvider`
- `PullRequestProvider`

### Factory behavior

Provider factories should accept a resolved execution context containing:

- product
- deployment
- URL
- auth mode
- credentials

They return the matching provider implementation or raise `UnsupportedError`.

## Output Design

### Supported formats

All commands should support:

- `table`
- `json`
- `yaml`

Global option:

- `--output json|yaml|table`

### Output rules

- Read commands default to `table`.
- Write commands return a structured success object rendered in the selected format.
- Delete-like operations require explicit `--yes`.
- List commands should support `--limit` and `--start`.
- Field selection should use a consistent `--fields`.

### Normalized fields

Resource output should expose stable CLI fields. For example, `jira issue get` should render normalized issue fields such as:

- `key`
- `summary`
- `status`
- `assignee`
- `reporter`
- `priority`
- `updated`

The CLI should not promise the raw backend shape as its contract.

## Error Handling

### Canonical error types

The CLI should map backend and transport failures into a small, stable error taxonomy:

- `ConfigError`
- `AuthError`
- `ConnectionError`
- `NotFoundError`
- `ValidationError`
- `ConflictError`
- `ServerError`
- `UnsupportedError`

### Exit codes

Recommended exit codes:

- `0`: success
- `2`: parameter or configuration error
- `3`: authentication or authorization error
- `4`: resource not found
- `5`: conflict
- `6`: network or timeout error
- `10`: unknown error

This mapping should be consistent across all products.

## Testing Strategy

### Unit tests

Unit tests should cover:

- config resolution precedence
- auth resolution
- output rendering
- schema normalization
- error mapping
- service-level behavior

These tests should not depend on live Atlassian instances.

### Provider contract tests

Provider contract tests should verify:

- correct translation from service inputs to provider calls
- correct normalization of backend responses
- correct exception mapping to canonical CLI errors

These tests may use mocks or fixtures around `atlassian-python-api`.

### Integration tests

Integration tests should be limited to a small smoke suite against real Server/DC instances, driven by environment configuration.

Suggested smoke coverage:

- `jira issue get`
- `confluence page get`
- `bitbucket repo list`

Integration tests should not be mandatory for all local development runs.

## Delivery Plan

### P0

CLI core:

- argument parsing
- profile loading
- config resolution
- auth resolution
- output rendering
- error mapping

### P1

Tier 1 resources:

- Jira `issue`, `project`, `user`
- Confluence `page`, `space`, `attachment`
- Bitbucket `project`, `repo`, `branch`, `pr`

### P2

Tier 2 resources:

- Jira `board`, `sprint`
- Confluence `search`
- Bitbucket `hook`, `branch-permission`

### P3

Tier 3 resources and future Cloud providers.

## Acceptance Criteria

The first release is complete when all of the following are true:

- Server/DC profiles work for Jira, Confluence, and Bitbucket.
- The v1 Tier 1 command set is implemented and documented.
- Commands support uniform config resolution via profiles, environment variables, and flags.
- Commands support `table`, `json`, and `yaml` output.
- Canonical error types map to stable exit codes.
- Core unit tests and provider contract tests cover the main execution paths.
- A minimal real-instance smoke suite exists for Jira, Confluence, and Bitbucket Server/DC.

## Future Expansion

The design deliberately reserves future work for:

- Atlassian Cloud providers
- `raw request` escape-hatch commands
- additional administrative resources
- richer query and filtering capabilities

Those features should be added by introducing new providers and new resource commands, not by breaking the existing command model.

## References

- `atlassian-python-api` repository: <https://github.com/atlassian-api/atlassian-python-api>
- Jira documentation: <https://atlassian-python-api.readthedocs.io/jira.html>
- Confluence documentation: <https://atlassian-python-api.readthedocs.io/confluence.html>
- Bitbucket documentation: <https://atlassian-python-api.readthedocs.io/bitbucket.html>
