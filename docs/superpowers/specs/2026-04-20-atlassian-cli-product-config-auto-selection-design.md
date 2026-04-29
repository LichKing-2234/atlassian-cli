# Atlassian CLI Product Config Auto-Selection Design

## Summary

Add first-run config template generation and product-specific top-level config blocks so `jira`, `confluence`, and `bitbucket` commands can resolve their own config without requiring `--profile`.

The new primary config shape is:

```toml
[headers]
# accessToken = "$(example-oauth token)"

[jira]
deployment = "server"
url = "https://jira.example.com"
auth = "basic"
username = "example-user"
token = "secret"

[jira.headers]
accessToken = "$(example-oauth token)"

[confluence]
deployment = "dc"
url = "https://confluence.example.com"
auth = "pat"
token = "secret"

[bitbucket]
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"
token = "secret"
```

When `~/.config/atlassian-cli/config.toml` does not exist, the CLI creates a template file containing commented examples for these sections. The CLI does not persist command-line values into the generated file.

## Goals

- Create `config.toml` automatically on first use when the default config path does not exist.
- Use top-level product blocks `[jira]`, `[confluence]`, and `[bitbucket]` as the primary config source when `--profile` is not supplied.
- Continue supporting repeated `--header` flags and config-backed `[headers]` and `[product.headers]` values.
- Keep `--profile` working as a compatibility path for legacy `[profiles.<name>]` configs.
- Produce clear guidance when the template was created but the selected product block is still incomplete.

## Non-Goals

- Persisting runtime flags such as `--url` or `--token` back into `config.toml`.
- Interactive setup prompts or wizards.
- Removing legacy `profiles` support in this change.
- Reworking command-line flags or auth semantics beyond config selection.

## Configuration Model

### Primary config shape

The default config file supports these top-level sections:

- `[headers]` for shared headers across all products
- `[jira]`
- `[confluence]`
- `[bitbucket]`

Each product section has the same shape as the current profile model:

- `deployment`
- `url`
- `auth`
- `username`
- `password`
- `token`
- optional nested `[<product>.headers]`

### Compatibility shape

Legacy profile config remains supported:

```toml
[profiles.prod_jira]
product = "jira"
deployment = "server"
url = "https://jira.example.com"
auth = "basic"
```

`--profile <name>` explicitly selects this compatibility path. If `--profile` is omitted, the CLI ignores legacy profiles and resolves from the matching top-level product block instead.

## Selection Rules

### Product-based auto-selection

The command namespace determines the config block:

- `atlassian jira ...` -> `[jira]`
- `atlassian confluence ...` -> `[confluence]`
- `atlassian bitbucket ...` -> `[bitbucket]`

This removes the current behavior of implicitly choosing the first profile in the file.

### Precedence

When `--profile` is not provided, runtime resolution order is:

1. explicit command-line flags such as `--url`, `--auth`, `--token`, and repeated `--header`
2. the selected product block `[jira]`, `[confluence]`, or `[bitbucket]`
3. top-level `[headers]` for shared header defaults

Within headers:

1. repeated `--header` overrides config-backed header names
2. `[<product>.headers]` overrides `[headers]`

When `--profile` is provided, runtime resolution order is:

1. explicit command-line flags such as `--url`, `--auth`, `--token`, and repeated `--header`
2. selected legacy profile `[profiles.<name>]`
3. top-level `[headers]`

This keeps compatibility mode explicit instead of mixing two config models implicitly.

## First-Run Template Generation

### Trigger

Template generation only happens when:

- the CLI is using the default config path, and
- that file does not exist

If the user passes a custom `--config-file` path and it does not exist, the CLI should not create it automatically. That path is treated as an explicit advanced override, and the CLI continues with an empty config model.

### Behavior

On first use with the default missing path, the CLI:

1. creates the parent directory `~/.config/atlassian-cli/` if needed
2. writes a template `config.toml`
3. continues command resolution using an empty config model

The generated file contains commented examples for:

- shared `[headers]`
- `[jira]`
- `[jira.headers]`
- `[confluence]`
- `[confluence.headers]`
- `[bitbucket]`
- `[bitbucket.headers]`
- optional legacy `profiles` note for compatibility

The generated template must be idempotent: existing files are never overwritten.

## Error Handling

If template generation occurred and the selected product block is missing or incomplete, and the user also did not provide `--url`, the CLI should fail with a clear actionable message such as:

- `Created ~/.config/atlassian-cli/config.toml. Fill in [jira] or pass --url.`

If the template already exists but the selected product block is still missing or incomplete, the CLI should fail with a similar product-specific message without implying a new file was created.

Legacy `--profile` errors stay explicit:

- `Unknown profile: <name>`

## Architecture

### Config models

Extend loaded config state to include optional product-scoped config entries:

- `jira`
- `confluence`
- `bitbucket`
- existing `profiles`
- shared `headers`

Each product block should reuse the same shape as a profile, minus the explicit `product` field because the block name already supplies that.

### Loader responsibilities

`config/loader.py` should:

- parse the new top-level product blocks
- continue parsing legacy profiles
- build a reusable in-memory config object with both models present
- expose a helper for writing the default template when needed

### CLI responsibilities

`cli.py` should:

- ensure the default config template exists before reading it
- determine the target product from the invoked subcommand
- if `--profile` is present, resolve via legacy profile lookup
- otherwise build a base product config from `[jira]`, `[confluence]`, or `[bitbucket]`
- keep inline `--url` mode working when config is incomplete

### Resolver responsibilities

`config/resolver.py` should continue owning runtime precedence merging, but it now receives either:

- a product-derived base config, or
- a legacy profile-derived base config

Header resolution remains unchanged apart from the new product block source.

## Testing

Add tests for:

- generating the default template when `~/.config/atlassian-cli/config.toml` is missing
- not overwriting an existing config file
- parsing top-level `[jira]`, `[confluence]`, and `[bitbucket]` blocks
- `jira` commands automatically using `[jira]` without `--profile`
- `confluence` commands automatically using `[confluence]` without `--profile`
- `bitbucket` commands automatically using `[bitbucket]` without `--profile`
- product-specific `[product.headers]` overriding top-level `[headers]`
- repeated `--header` overriding config-backed headers
- `--profile` continuing to resolve legacy `[profiles.<name>]`
- missing/incomplete selected product block producing product-specific guidance

## Documentation

Update `README.md` with:

- the new primary config shape using `[jira]`, `[confluence]`, and `[bitbucket]`
- an explanation that `--profile` is optional and mainly for legacy profile compatibility
- a note that the default config file is auto-created as a template on first use
- examples showing product-specific header configuration with `$(...)`
