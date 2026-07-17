# GitHub-Compatible Bitbucket API Command Design

Status: Approved

## Summary

Add a generic REST transport at `atlassian bitbucket api <endpoint>`. Its
command grammar, request construction, pagination controls, output modes, and
exit behavior follow `gh api` where those semantics apply to Bitbucket Server.
The initial documented and live-verified use case is the arbitrary-ref compare
capability requested by issue #31: compare diff, changes, and commits.

This is a raw API command, not a new normalized `compare` command group. It
does not transform Bitbucket response shapes into GitHub response shapes or
promise unified diff text when Bitbucket returns structured JSON.

## Fixed Baselines

- GitHub CLI: `gh v2.96.0`, tag commit
  `b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0`.
- Bitbucket: Atlassian Bitbucket Server `6.7.2`.
- Product command root: `atlassian bitbucket api`.

The pinned `gh` command, source, tests, and manual define API command behavior.
Bitbucket Server 6.7.2 REST documentation defines endpoint and pagination
behavior. Later baseline changes require a separate compatibility review.

## Goals

- Provide a generic authenticated Bitbucket REST command rather than three
  compare-specific subcommands.
- Match the applicable `gh api` REST argument names, aliases, defaults,
  validation, request construction, raw output, pagination, filtering, and exit
  behavior.
- Reuse the configured Bitbucket URL, authentication session, custom headers,
  TLS settings, and proxy settings.
- Live-verify the three Bitbucket compare endpoints needed by issue #31.
- Keep the command transport-oriented: return the server response without a
  normalized schema or `--output` option.

## Non-Goals

- GraphQL.
- `-t, --template` formatting.
- `--cache` response caching.
- `-p, --preview`, because GitHub vendor previews have no Bitbucket equivalent.
- `--hostname`, because the configured Bitbucket URL or root-level `--url`
  already selects the authenticated server. A command-local host override would
  bypass that configuration and authentication boundary.
- Bitbucket Cloud.
- A `bitbucket compare` command group or compare-specific response models.
- Normalizing Bitbucket payloads to GitHub Compare API payloads.
- Claiming that Bitbucket Server 6.7.2 returns unified diff text from
  `compare/diff`; its documented response is structured JSON.

## Public Command Contract

```text
atlassian bitbucket api <endpoint> [flags]
```

Supported flags:

```text
  -F, --field key=value       Add a typed parameter in key=value format
  -H, --header key:value      Add an HTTP request header
  -i, --include               Include response status and headers
      --input file            Read the request body from a file or stdin with -
  -q, --jq expression         Filter JSON output using jq syntax
  -X, --method method         HTTP method, default GET
      --paginate              Fetch every page
  -f, --raw-field key=value   Add a string parameter
      --silent                Do not print the response body
      --slurp                 Wrap paginated JSON pages in an outer array
      --verbose               Include the HTTP request and response
```

The command does not expose `--output`. By default it writes the response body
as returned by Bitbucket.

### Static Validation

Validation follows `gh api v2.96.0`:

- Exactly one endpoint argument is required.
- `--paginate` is rejected for non-GET requests.
- `--paginate` and `--input` are mutually exclusive.
- `--slurp` requires `--paginate`.
- `--slurp` and `--jq` are mutually exclusive.
- Only one of `--jq`, `--silent`, or `--verbose` may be used.
- Every `-f` and `-F` value must contain a valid key and, except for an empty
  array declaration such as `key[]`, an equals sign.
- Every `-H` value must contain a colon.
- `graphql` is rejected as unsupported before any request.

Usage and validation failures write to stderr and exit `1`.

## Endpoint Resolution

The configured Bitbucket URL remains the only origin. Absolute endpoint URLs
are rejected before any request so credentials cannot be redirected to another
host.

Endpoint forms are resolved as follows:

- `projects/DEMO/repos/example-repo/compare/changes` becomes
  `rest/api/1.0/projects/DEMO/repos/example-repo/compare/changes`.
- An endpoint beginning with `rest/` is used as the server-relative path
  unchanged, allowing other Bitbucket REST API roots.
- A single leading slash is ignored before applying these rules.
- Existing query parameters are preserved and merged with parameters produced
  by `-f` or `-F`.

The placeholders `{project}`, `{repo}`, and `{branch}` are available in the
endpoint and typed `-F` values. `{project}` and `{repo}` use the repository
resolution already implemented for the Bitbucket gh-compatibility commands.
`{branch}` uses the current Git branch and fails when it cannot be determined.
Repository discovery runs only when a placeholder is present.

## Field Semantics

`-f, --raw-field` always produces a string value. `-F, --field` applies the
same conversions as `gh api v2.96.0`:

- decimal integers become integers;
- `true` and `false` become booleans;
- `null` becomes a null value;
- `@path` reads the value from a file;
- `@-` reads the value from stdin;
- supported placeholders are expanded after typed conversion checks;
- every other value remains a string.

Nested objects use `key[subkey]=value`. Arrays use repeated `key[]=value`
fields, and `key[]` creates an empty array. Conflicting object, array, and scalar
declarations fail instead of silently overwriting earlier values. Raw fields are
applied before typed fields, matching the pinned `gh` implementation.

## Method And Body Semantics

- The default method is GET.
- If `-f`, `-F`, or `--input` is present and `-X` was not explicitly supplied,
  the method becomes POST.
- For GET requests, parsed fields are URL query parameters.
- For other methods without `--input`, parsed fields are a JSON request body.
  `Content-Type: application/json; charset=utf-8` is added unless overridden.
- With `--input`, the file or stdin is the unmodified request body and parsed
  fields are URL query parameters.
- `Accept: */*` is added unless overridden.
- Repeated `-H` values are accepted. A command-line header overrides a
  configured header with the same case-insensitive name.
- The outgoing method is uppercased.

The transport reuses the existing Bitbucket provider session. It must retain
Basic, PAT, or Bearer authentication, configured custom headers, certificate
verification, proxies, and request timeout behavior.

## Pagination

`--paginate` implements Bitbucket standard paging rather than GitHub `Link`
headers:

1. It is available only for GET requests.
2. It adds `limit=100` unless the endpoint or fields already provide `limit`.
3. A JSON object with `isLastPage: false` must provide `nextPageStart`.
4. The next request preserves all query parameters and replaces `start` with
   `nextPageStart`.
5. Paging stops for `isLastPage: true`, a response without standard Bitbucket
   page metadata, or a non-JSON response.
6. A repeated or non-advancing `nextPageStart` fails rather than looping.

Without `--slurp`, each JSON object page is emitted separately, matching
`gh api` object-page behavior. With `--slurp`, all JSON array or object pages
are wrapped in one outer JSON array. `--jq` runs independently for every page,
which supports commands such as `--paginate --jq '.values[]'`.

## Output Behavior

- The default output is the response body without a normalized wrapper.
- A `204` response writes no body.
- `--include` writes the HTTP version, status, reason, sorted response headers,
  a blank line, and then the body. Paginated included responses are separated by
  a blank line.
- `--silent` discards successful response bodies but does not suppress errors or
  change the exit status.
- `--jq` uses a real jq engine. String results are written without JSON quotes;
  structured, numeric, boolean, and null results use jq-compatible formatting.
- JSON may be colored when stdout is a TTY. Non-TTY output is uncolored.
- Successful non-silent output uses the existing pager rules. Piped output does
  not invoke a pager.
- `--verbose` writes the request and response to stdout. Authorization, proxy
  authorization, cookies, configured secret-bearing headers, and known token
  values are redacted. Request bodies are not treated as secrets and match the
  `gh api` observability contract.

The jq implementation adds the maintained Python `jq` binding as a runtime
dependency. The standalone PyOxidizer build and Linux glibc 2.28 check are part
of acceptance because this dependency contains native code.

## Error And Exit Behavior

- A successful HTTP status exits `0`.
- HTTP status `300` or greater preserves the response body, writes
  `atlassian: <message> (HTTP <status>)` to stderr, and exits `1`.
- Bitbucket JSON errors use non-empty `errors[].message` values. Otherwise the
  HTTP reason or `HTTP <status>` is used.
- Network and response-decoding failures write an actionable error to stderr and
  exit `1`.
- Missing authentication exits `4`.
- Keyboard interrupt or prompt abort exits `2`.
- JSON errors bypass `--jq`, matching `gh api`, so the original server body
  remains available for diagnosis.

## Architecture

The implementation uses the smallest existing boundaries that keep parsing,
transport, and terminal behavior independently testable:

- `src/atlassian_cli/products/bitbucket/commands/api.py`: Typer surface,
  preflight validation, output coordination, and gh-compatible exits.
- `src/atlassian_cli/products/bitbucket/api_fields.py`: pure field parsing,
  typed conversion, nesting, arrays, file input, and placeholder expansion.
- `src/atlassian_cli/products/bitbucket/services/api.py`: endpoint resolution,
  method/body construction, requests, and pagination.
- `src/atlassian_cli/products/bitbucket/providers/base.py`: one raw API request
  protocol method.
- `src/atlassian_cli/products/bitbucket/providers/server.py`: raw requests
  through the authenticated provider session.
- `src/atlassian_cli/cli.py`: `bitbucket api` registration.

No compare-specific schema, diff parser, repository clone, or generic framework
for Jira and Confluence is introduced.

## Compare Acceptance

The documented neutral examples use only public-safe placeholders:

```sh
atlassian bitbucket api -X GET \
  'projects/DEMO/repos/example-repo/compare/diff' \
  -f from='feature/DEMO-1234/example-change' \
  -f to='DEMO'

atlassian bitbucket api --paginate --jq '.values[]' -X GET \
  'projects/DEMO/repos/example-repo/compare/changes' \
  -f from='feature/DEMO-1234/example-change' \
  -f to='DEMO'

atlassian bitbucket api --paginate --jq '.values[]' -X GET \
  'projects/DEMO/repos/example-repo/compare/commits' \
  -f from='feature/DEMO-1234/example-change' \
  -f to='DEMO'
```

Live e2e extends the existing Bitbucket branch and pull request round trip so it
has two known refs. It verifies:

- `compare/diff` returns JSON containing a diff collection;
- `compare/changes` includes the neutral changed path;
- `compare/commits` includes the neutral test commit;
- pagination and jq work against a real Bitbucket Server 6.7.2 response;
- the existing configured authentication and extra headers require no changes.

## Repository Changes And Quality Gates

The implementation updates CLI help tests, command tests, provider/service
tests, README documentation, `tests/e2e/coverage_manifest.py`, and the affected
live e2e path. All examples and fixtures use the repository-approved neutral
placeholder set.

Before completion:

```sh
ruff format --check .
python -m pytest -q
ruff check README.md pyproject.toml src tests docs
ATLASSIAN_E2E=1 python -m pytest -q tests/e2e/test_bitbucket_live.py::<affected-test>
```

The shared repository virtual environment is used from the feature worktree.
The standalone macOS arm64 binary is rebuilt and smoke-tested, and CI must pass
the Linux manylinux 2.28 PyOxidizer build before the PR is considered complete.

## Review Decisions

- The API command is generic REST transport; compare is the initial acceptance
  case, not an endpoint allowlist.
- Applicable REST parameters and behavior match `gh api v2.96.0`.
- GraphQL, templates, caching, GitHub previews, and command-local hostname
  overrides are explicitly deferred or non-applicable.
- Raw Bitbucket responses are authoritative. No compare-specific normalization
  is added.
- The design intentionally avoids extending the API command abstraction to Jira
  or Confluence without a separate requirement.
