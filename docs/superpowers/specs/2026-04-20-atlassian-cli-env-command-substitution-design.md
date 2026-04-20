# Atlassian CLI Env Command Substitution Design

## Summary

Add TOML-backed env configuration for `ATLASSIAN_HEADER`, with optional shell-style command substitution inside the configured value. This lets users keep header generation in external tools such as `agora-oauth` while configuring the CLI entirely from `~/.config/atlassian-cli/config.toml`.

The supported target syntax is:

```toml
[env]
ATLASSIAN_HEADER = "accessToken: $(agora-oauth token)"

[profiles.code]
product = "bitbucket"
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"

[profiles.code.env]
ATLASSIAN_HEADER = "accessToken: $(agora-oauth token --profile code)"
```

At runtime, the CLI resolves the configured string into a single header line and feeds it through the existing `ATLASSIAN_HEADER` parsing path.

## Goals

- Support top-level `[env]` defaults in `config.toml`.
- Support per-profile `[profiles.<name>.env]` overrides in `config.toml`.
- Allow `ATLASSIAN_HEADER` to embed one or more shell-style `$(...)` command substitutions.
- Preserve existing precedence where CLI flags and real process environment variables still override config file values.
- Reuse the existing header parsing and session patching behavior after config resolution.

## Non-Goals

- General-purpose command substitution for arbitrary profile fields such as `url`, `username`, or `token`.
- General-purpose command substitution for arbitrary config env keys.
- Full shell language support in config values beyond `$(...)` substitutions for `ATLASSIAN_HEADER`.
- Persisting evaluated command output back into `config.toml`.
- Caching command output across CLI invocations.

## Configuration Model

### Supported TOML shape

The config file gains two optional env tables:

- top-level `[env]`
- profile-scoped `[profiles.<name>.env]`

Both tables are string maps. For this feature, only the `ATLASSIAN_HEADER` key is supported. Any other key inside config-backed env tables should be rejected as invalid configuration so users do not assume broader env support exists.

### Resolution precedence

`ATLASSIAN_HEADER` is resolved in this order:

1. repeated `--header` flags
2. process environment variable `ATLASSIAN_HEADER`
3. selected profile `[profiles.<name>.env].ATLASSIAN_HEADER`
4. top-level `[env].ATLASSIAN_HEADER`

This keeps explicit runtime inputs above config defaults while letting top-level config provide a shared fallback.

## Command Substitution Rules

### Supported syntax

`ATLASSIAN_HEADER` may contain literal text plus one or more `$(...)` command substitutions.

Examples:

- `ATLASSIAN_HEADER = "accessToken: $(agora-oauth token)"`
- `ATLASSIAN_HEADER = "Authorization: Bearer $(agora-oauth token --audience bitbucket)"`

### Scope

Command substitution is only evaluated for config-backed `ATLASSIAN_HEADER` values. The CLI must not evaluate `$(...)` found in process environment variables or values supplied through `--header`; those continue to be treated as already-resolved inputs.

### Evaluation behavior

For each `$(...)` occurrence:

1. Extract the command contents without the wrapping `$(` and `)`.
2. Execute the command with `/bin/sh -lc <command>`.
3. Capture `stdout`.
4. Trim surrounding whitespace from the captured output.
5. Replace the original `$(...)` expression with the trimmed output.

The final substituted string is then parsed as one complete header line using the existing header parser.

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

- config env tables contain unsupported keys
- a `$(...)` substitution is malformed
- a command body is empty
- `/bin/sh -lc` exits non-zero
- substituted command output is empty after trimming
- substituted command output contains a newline
- the final resolved header string is not a valid `Name: value` header line

The error should identify whether the failing source was the top-level `[env]` or a specific profile env table so users can fix the correct config block quickly.

## Security Model

- `config.toml` must be treated as trusted local configuration because this feature executes local shell commands from it.
- Command substitution is opt-in and limited to `ATLASSIAN_HEADER`.
- Evaluated header values are runtime-only and must not be written back to disk.
- Error messages should avoid echoing sensitive resolved header values.

## Architecture

### Config loading

Extend config models and loader behavior to capture:

- top-level config env values
- profile-level env values alongside existing profile fields

### Resolution flow

1. Load top-level config env map and selected profile env map.
2. Resolve `ATLASSIAN_HEADER` according to precedence.
3. If the winning config-backed value contains `$(...)`, evaluate substitutions.
4. Parse the resolved string with the existing `parse_cli_headers` helper.
5. Merge resulting headers with CLI flag headers using existing precedence rules.

The rest of the request pipeline remains unchanged.

### Implementation boundaries

- `config/models.py` owns typed representation of top-level and profile env maps.
- `config/loader.py` owns TOML parsing and validation of supported config env keys.
- a new focused helper module should own `ATLASSIAN_HEADER` substitution evaluation and related validation
- `config/resolver.py` owns precedence merging across CLI flags, process env, profile config env, and top-level config env

## Testing

Add tests for:

- loading top-level `[env]` and profile `[profiles.<name>.env]`
- rejecting unsupported config env keys
- top-level config env supplying `ATLASSIAN_HEADER`
- profile config env overriding top-level config env
- process environment `ATLASSIAN_HEADER` overriding config env values
- repeated `--header` overriding both process env and config env values
- successful substitution for `accessToken: $(agora-oauth token)`
- multiple substitutions in one configured header value
- malformed substitution syntax
- empty command body
- command execution failure
- empty command output
- multiline command output rejection
- invalid resolved header format rejection

## Documentation

Update `README.md` with:

- the new `[env]` and `[profiles.<name>.env]` syntax
- a concrete `agora-oauth` example
- precedence notes explaining that process env and `--header` still win over config-backed values
- a short warning that config-based command substitution executes local shell commands
