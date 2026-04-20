# Atlassian CLI Config Headers Command Substitution Design

## Summary

Add TOML-backed header configuration, with optional shell-style command substitution inside configured header values. This lets users keep header generation in external tools such as `agora-oauth` while configuring the CLI entirely from `~/.config/atlassian-cli/config.toml`.

The supported target syntax is:

```toml
[headers]
accessToken = "$(agora-oauth token)"

[profiles.code]
product = "bitbucket"
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"

[profiles.code.headers]
accessToken = "$(agora-oauth token --profile code)"
```

At runtime, the CLI resolves the configured header map into request headers and merges it with repeated `--header` flags.

## Goals

- Support top-level `[headers]` defaults in `config.toml`.
- Support per-profile `[profiles.<name>.headers]` overrides in `config.toml`.
- Allow configured header values to embed one or more shell-style `$(...)` command substitutions.
- Preserve explicit CLI flag precedence where repeated `--header` values override config file values.
- Reuse the existing session patching behavior after config resolution.

## Non-Goals

- General-purpose command substitution for arbitrary profile fields such as `url`, `username`, or `token`.
- Full shell language support in config values beyond `$(...)` substitutions inside configured header values.
- Persisting evaluated command output back into `config.toml`.
- Caching command output across CLI invocations.

## Header Configuration Model

### Supported TOML shape

The config file gains two optional header tables:

- top-level `[headers]`
- profile-scoped `[profiles.<name>.headers]`

Both tables are string-to-string maps. Each key is treated as the target HTTP header name. Each value is either a literal string or a string containing one or more `$(...)` command substitutions.

### Resolution precedence

Header maps are resolved in this order:

1. repeated `--header` flags
2. selected profile `[profiles.<name>.headers]`
3. top-level `[headers]`

Config-backed header maps are merged by header name, so profile-scoped entries override top-level entries with the same header name. Repeated `--header` flags override the same header name from either config table.

## Command Substitution Rules

### Supported syntax

Any config-backed header value may contain literal text plus one or more `$(...)` command substitutions.

Examples:

- `accessToken = "$(agora-oauth token)"`
- `Authorization = "Bearer $(agora-oauth token --audience bitbucket)"`

### Scope

Command substitution is only evaluated for config-backed header values. The CLI must not evaluate `$(...)` found in values supplied through `--header`; those continue to be treated as already-resolved inputs.

### Evaluation behavior

For each `$(...)` occurrence:

1. Extract the command contents without the wrapping `$(` and `)`.
2. Execute the command with `/bin/sh -lc <command>`.
3. Capture `stdout`.
4. Trim surrounding whitespace from the captured output.
5. Replace the original `$(...)` expression with the trimmed output.

The final substituted string becomes the resolved header value for that header name.

### Syntax limits

To keep the implementation explicit and testable:

- support one or more non-empty `$(...)` substitutions in a single value
- support literal text before, between, and after substitutions
- do not support nested command substitutions such as `$(echo $(foo))`
- do not support backtick command substitution
- do not expand `$VAR` or other shell syntax in the surrounding literal text

If the value contains unbalanced or malformed `$(...)` syntax, config resolution should fail with a `ConfigError`.

## Error Handling

Config resolution should raise a `ConfigError` with a clear message when:

- a `$(...)` substitution is malformed
- a command body is empty
- `/bin/sh -lc` exits non-zero
- substituted command output is empty after trimming
- substituted command output contains a newline
- a config header value is not a string

The error should identify whether the failing source was the top-level `[headers]` table or a specific profile header table so users can fix the correct config block quickly.

## Security Model

- `config.toml` must be treated as trusted local configuration because this feature executes local shell commands from it.
- Command substitution is opt-in and limited to config-backed header values.
- Evaluated header values are runtime-only and must not be written back to disk.
- Error messages should avoid echoing sensitive resolved header values.

## Architecture

### Config loading

Extend config models and loader behavior to capture:

- top-level config header values
- profile-level header values alongside existing profile fields

### Resolution flow

1. Load top-level config header map and selected profile header map.
2. Merge top-level headers with profile headers by header name.
3. Evaluate `$(...)` substitutions in the merged config-backed header values.
4. Merge resulting headers with CLI flag headers using existing precedence rules.

The rest of the request pipeline remains unchanged.

### Implementation boundaries

- `config/models.py` owns typed representation of top-level and profile header maps.
- `config/loader.py` owns TOML parsing for top-level and profile header tables.
- a new focused helper module should own header value substitution evaluation and related validation
- `config/resolver.py` owns precedence merging across CLI flags, profile config headers, and top-level config headers

## Testing

Add tests for:

- loading top-level `[headers]` and profile `[profiles.<name>.headers]`
- top-level config headers supplying request headers
- profile config headers overriding top-level config headers
- repeated `--header` overriding both top-level and profile config headers
- successful substitution for `accessToken = "$(agora-oauth token)"`
- multiple substitutions in one configured header value
- malformed substitution syntax
- empty command body
- command execution failure
- empty command output
- multiline command output rejection
- non-string config header value rejection

## Documentation

Update `README.md` with:

- the new `[headers]` and `[profiles.<name>.headers]` syntax
- a concrete `agora-oauth` example
- precedence notes explaining that repeated `--header` still wins over config-backed values
- a short warning that config-based command substitution executes local shell commands
