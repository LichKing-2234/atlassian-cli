# Atlassian CLI Remove Profiles Design

## Summary

Remove legacy `[profiles.<name>]` configuration and the `--profile` flag. The CLI keeps only top-level product configuration blocks plus shared and product-scoped headers.

The supported config shape becomes:

```toml
[headers]
# accessToken = "$(agora-oauth token)"

[jira]
deployment = "server"
url = "https://jira.example.com"
auth = "basic"
username = "alice"
token = "secret"

[jira.headers]
accessToken = "$(agora-oauth token)"

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

`jira`, `confluence`, and `bitbucket` commands always resolve from their matching top-level block unless explicit inline flags such as `--url` override fields at runtime.

## Goals

- Remove `[profiles.<name>]` parsing entirely.
- Remove the `--profile` CLI option entirely.
- Keep the product-specific top-level blocks `[jira]`, `[confluence]`, and `[bitbucket]` as the only supported persisted config model.
- Continue auto-creating the default config template on first use.
- Continue supporting shared `[headers]`, product-specific `[product.headers]`, and repeated `--header` flags.

## Non-Goals

- Automatic migration from legacy profiles to top-level product blocks.
- Backward-compatible parsing of old profile-based config files.
- Interactive migration prompts or wizards.
- Changing runtime auth semantics beyond config source selection.

## Supported Configuration Model

The config file supports only these top-level sections:

- `[headers]`
- `[jira]`
- `[jira.headers]`
- `[confluence]`
- `[confluence.headers]`
- `[bitbucket]`
- `[bitbucket.headers]`

Each product block has this shape:

- `deployment`
- `url`
- `auth`
- `username`
- `password`
- `token`

Each product block may also have an optional nested header table.

## Removed Configuration Model

These are no longer supported:

- `[profiles.<name>]`
- `[profiles.<name>.headers]`
- `--profile`

If the loader detects a `profiles` table in `config.toml`, it should raise a `ConfigError` explaining that profile-based configuration has been removed and the user must migrate to top-level product blocks.

## Selection Rules

The command namespace determines the config block:

- `atlassian jira ...` -> `[jira]`
- `atlassian confluence ...` -> `[confluence]`
- `atlassian bitbucket ...` -> `[bitbucket]`

Runtime precedence remains:

1. explicit command-line flags such as `--url`, `--auth`, `--token`, and repeated `--header`
2. the selected product block
3. top-level `[headers]`

Within headers:

1. repeated `--header` overrides config-backed header names
2. `[<product>.headers]` overrides `[headers]`

## First-Run Template Generation

When the default config path `~/.config/atlassian-cli/config.toml` does not exist, the CLI:

1. creates the parent directory if needed
2. writes a commented template file using only the supported top-level product blocks
3. continues command resolution with an empty config model

If the selected product block is still missing or incomplete and no `--url` was provided, the CLI should fail with a clear message telling the user to fill in that product block or pass `--url`.

The generated template must not include any legacy `profiles` examples.

## Error Handling

Configuration errors should be explicit and actionable:

- Missing selected product block:
  - `Fill in [jira] in ~/.config/atlassian-cli/config.toml or pass --url.`
- Template just created and selected product block still missing:
  - `Created ~/.config/atlassian-cli/config.toml. Fill in [jira] or pass --url.`
- Legacy profile config present:
  - `Profile-based config [profiles.*] has been removed. Migrate to top-level [jira], [confluence], or [bitbucket].`

Command-line behavior should also be explicit:

- `--profile` is removed from the CLI surface and should not appear in help output
- passing `--profile` should be treated as an unknown option by Typer

## Architecture

### Config models

The loaded config state should include:

- shared `headers`
- optional `jira`
- optional `confluence`
- optional `bitbucket`

It should no longer include `profiles`.

### Loader responsibilities

`config/loader.py` should:

- parse supported top-level product blocks
- reject any `profiles` table
- validate the supported config model

### CLI responsibilities

`cli.py` should:

- stop declaring the `--profile` option
- ensure the default template exists on first use
- determine the target product from the invoked subcommand
- derive the base runtime config from the matching top-level product block
- keep inline `--url` mode working for ad hoc usage

### Template responsibilities

`config/template.py` should:

- generate a template containing only supported sections
- remove all legacy compatibility comments referencing profiles

## Testing

Add or update tests for:

- default template generation with no legacy profile examples
- top-level `[jira]`, `[confluence]`, and `[bitbucket]` parsing
- `jira`, `confluence`, and `bitbucket` commands automatically using their matching blocks
- `[headers]` and `[product.headers]` merging
- repeated `--header` overriding config-backed headers
- legacy `profiles` config causing a `ConfigError`
- CLI help output not containing `--profile`
- passing `--profile` producing an unknown-option failure

## Documentation

Update `README.md` and any active design docs to:

- remove profile-based examples
- present top-level product blocks as the only supported config shape
- explain first-run template generation
- explain product-specific header configuration with `$(...)`
