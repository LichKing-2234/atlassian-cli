# Atlassian CLI Environment-Backed Config and Export Design

## Summary

Add explicit environment-variable interpolation to config-backed workflows so users can keep product config in `config.toml` without hardcoding secrets or host-specific values directly in the file.

The design adds three related capabilities:

- `${VAR_NAME}` interpolation for product config fields
- `${VAR_NAME}` interpolation for configured headers, while preserving existing `$(...)` command substitution for headers
- a new `atlassian env` command that exports resolved config as shell `export` statements for workflows such as `eval "$(atlassian env)"`

The existing direct runtime overrides remain supported:

- CLI flags still have highest precedence
- existing global environment overrides such as `ATLASSIAN_URL` and `ATLASSIAN_TOKEN` still work
- config-backed `${...}` values remain explicit and opt-in

## Goals

- Let users keep `config.toml` free of hardcoded credentials and host-specific values.
- Support per-product environment-backed values for `jira`, `confluence`, and `bitbucket`.
- Support environment-backed values for product header configuration in addition to existing `$(...)` header command substitution.
- Keep environment-backed config explicit in the file instead of silently introducing more fallback behavior.
- Add an `atlassian init --env-template` mode that writes standard `${...}` references instead of prompting for real values.
- Add an `atlassian env` command that emits resolved shell exports derived from the current config.
- Preserve existing runtime precedence rules across flags, process environment, and config.
- Update tests and user-facing documentation with approved neutral example data.

## Non-Goals

- Replacing existing global runtime overrides such as `ATLASSIAN_URL`, `ATLASSIAN_USERNAME`, `ATLASSIAN_PASSWORD`, or `ATLASSIAN_TOKEN`.
- Introducing a separate secret store, keychain integration, or encrypted config file.
- Adding shell command execution to normal product fields such as `url`, `auth`, or `token`.
- Adding default-value interpolation such as `${VAR:-default}` in the first phase.
- Adding escaping rules for literal `${...}` sequences in the first phase.
- Adding PowerShell-specific export output in the first phase.
- Loading `.env` files automatically during normal CLI execution.

## Config Syntax

Product config fields may contain `${VAR_NAME}` references.

Example:

```toml
[jira]
deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
url = "${ATLASSIAN_JIRA_URL}"
auth = "${ATLASSIAN_JIRA_AUTH}"
username = "${ATLASSIAN_JIRA_USERNAME}"
token = "${ATLASSIAN_JIRA_TOKEN}"
```

Interpolation applies to product-block scalar fields, including:

- `deployment`
- `url`
- `auth`
- `username`
- `password`
- `token`

Header values may also contain `${VAR_NAME}` references.

Example:

```toml
[headers]
X-Request-Source = "${ATLASSIAN_HEADER_X_REQUEST_SOURCE}"

[bitbucket]
deployment = "${ATLASSIAN_BITBUCKET_DEPLOYMENT}"
url = "${ATLASSIAN_BITBUCKET_URL}"
auth = "${ATLASSIAN_BITBUCKET_AUTH}"

[bitbucket.headers]
Authorization = "Bearer ${ATLASSIAN_BITBUCKET_HEADER_AUTHORIZATION}"
accessToken = "$(example-oauth token --host ${ATLASSIAN_BITBUCKET_URL})"
```

Header values keep both dynamic mechanisms:

- `${...}` reads from the process environment
- `$(...)` executes a trusted local command

Only header values support command execution. Normal product config fields do not.

## Resolution Rules

### Scope

The CLI should resolve only the product block required by the current command, plus top-level and product-level headers relevant to that product.

This avoids unrelated failures such as a missing Confluence variable blocking a Jira command.

### Parse Order

The current config loader validates into `ProductConfig` too early for enum-backed fields such as `deployment` and `auth`. To support `${...}` for those fields, resolution must happen before full model validation.

The runtime flow should become:

1. Read raw TOML data from `config.toml`
2. Select the active product block for the current command
3. Resolve `${...}` in that product block
4. Resolve `${...}` in `[headers]` and `[product.headers]`
5. For header values only, resolve `$(...)` after `${...}`
6. Validate the resolved product block into `ProductConfig` and `ProfileConfig`
7. Apply existing runtime precedence in `resolve_runtime_context()`

### Precedence

Resolved config values should continue to participate in the existing precedence model:

1. CLI flags such as `--url`, `--auth`, `--username`, `--password`, `--token`, and `--header`
2. existing global process environment overrides such as `ATLASSIAN_URL`, `ATLASSIAN_USERNAME`, `ATLASSIAN_PASSWORD`, and `ATLASSIAN_TOKEN`
3. resolved config values from `${...}` or plain literal config values

This keeps `${...}` explicit without changing the CLI's existing override behavior.

### Interpolation Semantics

`${VAR_NAME}` should support:

- full-value substitution such as `"${ATLASSIAN_JIRA_TOKEN}"`
- embedded substitution such as `"https://${ATLASSIAN_JIRA_HOST}"`
- multiple substitutions inside one string

The first phase should require valid environment variable names and fail hard on malformed input or missing values.

## `init --env-template`

Add a new mode:

```bash
atlassian init jira --env-template
atlassian init confluence --env-template
atlassian init bitbucket --env-template
atlassian init --env-template
```

Default `init` behavior stays unchanged. Without `--env-template`, `init` continues to prompt for or accept real config values and writes literal values into `config.toml`.

With `--env-template`, `init` writes standard environment-backed placeholders instead of prompting for actual values.

Example output:

```toml
[jira]
deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
url = "${ATLASSIAN_JIRA_URL}"
auth = "${ATLASSIAN_JIRA_AUTH}"
username = "${ATLASSIAN_JIRA_USERNAME}"
password = "${ATLASSIAN_JIRA_PASSWORD}"
token = "${ATLASSIAN_JIRA_TOKEN}"

[jira.headers]
Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"
```

Confluence and Bitbucket use the same fixed naming pattern with their product name substituted.

In `--env-template` mode:

- the command does not prompt for `deployment`, `url`, `auth`, `username`, `password`, or `token`
- non-interactive invocation does not require those options
- overwrite behavior remains unchanged

`atlassian init --env-template` without a product argument should still ask which products to configure in order, matching the current wizard structure.

## Default Template

The default generated `~/.config/atlassian-cli/config.toml` template should shift from commented literal secrets to commented `${...}` examples so first-use guidance matches the recommended path.

Example shape:

```toml
[headers]
# X-Request-Source = "${ATLASSIAN_HEADER_X_REQUEST_SOURCE}"

[jira]
# deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
# url = "${ATLASSIAN_JIRA_URL}"
# auth = "${ATLASSIAN_JIRA_AUTH}"
# username = "${ATLASSIAN_JIRA_USERNAME}"
# token = "${ATLASSIAN_JIRA_TOKEN}"

[jira.headers]
# Authorization = "${ATLASSIAN_JIRA_HEADER_AUTHORIZATION}"
# accessToken = "$(example-oauth token --host ${ATLASSIAN_JIRA_URL})"
```

This keeps the first generated file useful without pushing users toward hardcoded `secret` examples.

## `atlassian env` Command

Add a new top-level command:

```bash
atlassian env
```

The first-phase output target is POSIX shell syntax for workflows such as:

```bash
eval "$(atlassian env)"
```

### Command Contract

- Read the current config file using the same config path selection rules as the rest of the CLI.
- Resolve all configured product blocks and configured headers into concrete values.
- Print one `export NAME='value'` line per resolved variable.
- Exit non-zero when any configured value cannot be resolved.

The command is a local configuration utility. It does not call Jira, Confluence, or Bitbucket APIs.

### Source of Truth

`atlassian env` derives its output from `config.toml`.

It is not a second config store. It does not persist values elsewhere, and it does not invent fallback values for unresolved placeholders.

If a configured value references `${ATLASSIAN_JIRA_TOKEN}` and that variable is absent at runtime, `atlassian env` should fail instead of emitting a partial export file.

### Output Naming

Product field variables use fixed names:

- `ATLASSIAN_JIRA_DEPLOYMENT`
- `ATLASSIAN_JIRA_URL`
- `ATLASSIAN_JIRA_AUTH`
- `ATLASSIAN_JIRA_USERNAME`
- `ATLASSIAN_JIRA_PASSWORD`
- `ATLASSIAN_JIRA_TOKEN`
- `ATLASSIAN_CONFLUENCE_DEPLOYMENT`
- `ATLASSIAN_CONFLUENCE_URL`
- `ATLASSIAN_CONFLUENCE_AUTH`
- `ATLASSIAN_CONFLUENCE_USERNAME`
- `ATLASSIAN_CONFLUENCE_PASSWORD`
- `ATLASSIAN_CONFLUENCE_TOKEN`
- `ATLASSIAN_BITBUCKET_DEPLOYMENT`
- `ATLASSIAN_BITBUCKET_URL`
- `ATLASSIAN_BITBUCKET_AUTH`
- `ATLASSIAN_BITBUCKET_USERNAME`
- `ATLASSIAN_BITBUCKET_PASSWORD`
- `ATLASSIAN_BITBUCKET_TOKEN`

Header exports use a normalized suffix:

- top-level `[headers]`: `ATLASSIAN_HEADER_<NORMALIZED_NAME>`
- product headers: `ATLASSIAN_<PRODUCT>_HEADER_<NORMALIZED_NAME>`

Normalization rules:

- insert `_` between lowercase-to-uppercase word boundaries
- replace non-alphanumeric characters with `_`
- collapse repeated `_`
- uppercase the final name

Examples:

- `accessToken` -> `ACCESS_TOKEN`
- `X-Request-Source` -> `X_REQUEST_SOURCE`
- `Authorization` -> `AUTHORIZATION`

### Output Safety

Values must be safely single-quoted for shell output. Embedded single quotes must be escaped correctly for POSIX shell consumption.

The command should not print explanatory prose to stdout, because the primary contract is command substitution into `eval`.

## Architecture

Add a dedicated config interpolation module, for example:

```text
src/atlassian_cli/config/env_interpolation.py
```

Responsibilities:

- parse `${...}` references in strings
- validate variable names
- resolve one product block from raw TOML data
- resolve header maps before command substitution
- attach source-path information to errors

Keep this separate from `config/header_substitution.py` because the safety model differs:

- env interpolation reads existing process state
- header substitution executes local commands

Suggested layering:

```text
raw TOML -> env interpolation -> header command substitution -> config models -> runtime context
```

`load_config()` should remain available for already-resolved literal config, but the CLI entry path for product commands and the new `env` command should use a raw-data path before final model validation.

Add a new command module for the export command, for example:

```text
src/atlassian_cli/commands/env.py
```

Register it at the root level and update the CLI command surface tests accordingly.

## Error Handling

Expected hard failures:

- missing environment variable referenced by `${...}`
- malformed interpolation syntax
- invalid variable name in `${...}`
- invalid enum value after interpolation, such as unsupported `deployment` or `auth`
- header command failure after `${...}` resolution
- unresolved value during `atlassian env`

Errors should identify the config source precisely, for example:

- `Missing environment variable ATLASSIAN_JIRA_TOKEN for [jira].token`
- `Malformed environment interpolation in [bitbucket].url`
- `Missing environment variable ATLASSIAN_BITBUCKET_URL for [bitbucket.headers].accessToken`

The CLI should not:

- silently treat missing `${...}` as an empty string
- leave unresolved `${...}` text in the final runtime config
- emit partial `atlassian env` output after a failure

## Documentation

Update `README.md` with:

- config examples that use `${...}` instead of literal `secret` placeholders for recommended flows
- a dedicated environment-backed config section
- `atlassian init --env-template` examples
- `eval "$(atlassian env)"` usage guidance
- a clear distinction between `${...}` environment interpolation and `$(...)` header command substitution

Update command help text for:

- `init`
- the new `env` command

All examples must continue to use neutral placeholder values and example domains only.

## Testing

Add focused tests for interpolation behavior:

- product fields resolve `${...}` before model validation
- `deployment` and `auth` accept env-backed values
- only the active product block is resolved during normal product command execution
- embedded interpolation works inside larger strings
- malformed or missing `${...}` fails with source-aware errors

Add focused header tests:

- `${...}` works in top-level `[headers]`
- `${...}` works in `[product.headers]`
- header resolution applies `${...}` before `$(...)`
- header command substitution still works when the command string contains env-backed pieces

Add `init` and template tests:

- `init --env-template PRODUCT` writes fixed `${...}` references
- `init --env-template` without a product still prompts for products in order
- `init --env-template` preserves overwrite protections
- default config template uses commented `${...}` examples

Add `env` command tests:

- `atlassian env` exports all configured product blocks
- `atlassian env` exports normalized top-level and product-level header names
- values are shell-quoted correctly
- unresolved config causes non-zero exit and no partial stdout contract

Update command-surface coverage:

- add `env` to `tests/e2e/coverage_manifest.py`
- point `env` at a local automated owner test because it is not a live Atlassian API command

Live `ATLASSIAN_E2E=1` verification is not required for `env`, because the command exercises local config parsing only. Product-command live e2e coverage remains unchanged by the addition of local configuration utilities.
