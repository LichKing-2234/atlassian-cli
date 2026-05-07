# Atlassian CLI Init Command Design

## Summary

Add a top-level `atlassian init [PRODUCT]` command that creates or updates the local config file through an interactive setup flow, while also supporting fully parameterized non-interactive use for scripts.

The command configures the existing product blocks:

```toml
[headers]

[jira]
deployment = "server"
url = "https://jira.example.com"
auth = "basic"
username = "example-user"
token = "secret"

[jira.headers]
```

`atlassian init jira` configures only `[jira]`. `atlassian init` starts a first-run wizard that asks, in order, whether to configure `jira`, `confluence`, and `bitbucket`.

## Goals

- Provide an explicit first-run setup command instead of requiring users to discover config generation through a failed product command.
- Keep the existing first-use template generation behavior for compatibility.
- Support one-product setup with `atlassian init PRODUCT`.
- Support full setup with `atlassian init`, prompting for each product in order.
- Support non-interactive setup through flags.
- Avoid accidental overwrites of existing product config.
- Validate config data before writing.

## Non-Goals

- Removing the current automatic default-template generation.
- Testing credentials by calling Atlassian APIs during init.
- Introducing profiles or reintroducing `--profile`.
- Adding secret storage outside `config.toml`.
- Managing environment variables or shell startup files.

## Command Shape

The command is top-level:

```bash
atlassian init
atlassian init jira
atlassian init confluence
atlassian init bitbucket
```

Supported options:

- `--config-file PATH`
- `--deployment server|dc|cloud`
- `--url URL`
- `--auth basic|pat|bearer`
- `--username USERNAME`
- `--password PASSWORD`
- `--token TOKEN`
- `--force`

Examples:

```bash
atlassian init jira
atlassian init bitbucket --deployment dc --url https://bitbucket.example.com --auth pat --token secret
atlassian init confluence --force --deployment server --url https://confluence.example.com --auth basic --username example-user --token secret
```

## User Flow

### Product Argument Provided

When `PRODUCT` is present, `init` configures only that product.

If required values are missing and stdin is interactive, `init` prompts for the missing values. Sensitive values use hidden input.

If required values are missing and stdin is not interactive, `init` exits with a usage error and does not write partial config.

### Product Argument Omitted

When `PRODUCT` is omitted, `init` runs a full setup wizard. It asks whether to configure each product in this order:

1. `jira`
2. `confluence`
3. `bitbucket`

Skipped products are left unchanged. Selected products use the same prompt and validation rules as single-product setup.

The same product-scoped options may be provided with `atlassian init`, but they only apply to products the wizard configures. This keeps the first implementation simple and predictable. Users who need different values per product can run `atlassian init PRODUCT` once per product.

## Required Values

Each configured product block must include:

- `deployment`
- `url`
- `auth`

Authentication-specific requirements:

- `pat` requires `token`
- `bearer` requires `token`
- `basic` prompts for `username` and one credential value

For `basic`, the credential value may be written as `token` by default. `password` remains supported when explicitly provided with `--password`, matching the existing runtime model.

## Overwrite Behavior

Existing product blocks are protected by default.

Interactive behavior:

- If the target product block already exists, ask whether to overwrite it.
- If the user declines, leave that product unchanged.
- In the full wizard, declining overwrite for one product continues to the next product.

Non-interactive behavior:

- If the target product block already exists and `--force` is not provided, exit with a usage error.
- If `--force` is provided, replace the target product block.

This applies per product. `--force` does not remove unrelated product blocks.

## File Behavior

Default config path remains:

```text
~/.config/atlassian-cli/config.toml
```

If the config file does not exist, `init` creates the parent directory and starts from the existing default template shape.

If the config file exists, `init` reads it, preserves unrelated sections, and replaces only the selected product block and its nested `[product.headers]` block.

The selected product block is replaced as a whole instead of merged field-by-field. This avoids stale auth fields, for example an old `username` remaining after changing from `basic` to `pat`.

Before writing, `init` builds an in-memory product config and validates it with the existing config model. Failed validation exits without writing.

## Architecture

Add a small init command module, for example `src/atlassian_cli/commands/init.py`, and register it from the root Typer app as `init`.

Responsibilities:

- Parse the optional product argument and init-specific options.
- Decide whether the session is interactive.
- Prompt for missing values when allowed.
- Enforce overwrite behavior.
- Assemble a validated `ProductConfig`.
- Delegate TOML read/write details to config-layer helpers.

The config layer should own file operations through focused helpers, for example:

- loading existing config text into a mutable representation
- creating the default config skeleton when the file is absent
- replacing one product block
- writing the final text atomically enough for normal CLI use

The implementation should use a TOML-aware approach where practical instead of ad hoc line editing. If the dependency set does not already include a TOML writer, a narrow local writer is acceptable because the supported public config shape is small and well defined.

## Error Handling

Errors should be actionable and should not expose hidden input values.

Expected failures:

- unsupported product argument
- missing required non-interactive option
- existing product config without `--force` in non-interactive mode
- invalid enum values for `deployment` or `auth`
- invalid existing `config.toml`
- file write failure

Partial writes are not allowed. If any selected product fails validation before the write phase, the command leaves the config file unchanged.

## Documentation

Update README with:

- `atlassian init` as the recommended first setup command
- `atlassian init PRODUCT` examples
- non-interactive examples using neutral placeholder values
- a note that the existing default template is still auto-created on first product command

Sample data must use the repository-approved neutral placeholder set and example domains only.

## Testing

Add focused tests for:

- single-product interactive init writes the requested product block
- full wizard prompts for `jira`, `confluence`, and `bitbucket` in order
- skipped products remain unchanged
- non-interactive complete options write config without prompts
- non-interactive missing required values fails without writing
- existing product blocks are not overwritten by default
- interactive overwrite confirmation replaces only the selected product
- non-interactive overwrite requires `--force`
- current first-use default template behavior still works
- root help lists `init`

`tests/e2e/coverage_manifest.py` does not need a new product API entry because `init` is a local config command, not a Jira, Confluence, or Bitbucket API subcommand.
