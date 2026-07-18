# Bitbucket PR List Native Compatibility Design

## Goal

Keep `bitbucket pr list` consistent with the repository's existing Bitbucket PR
commands while retaining the newer repository selector and automatic pagination.
The command must expose Bitbucket-native pull request states instead of replacing
them with GitHub state names.

## Command Grammar

The command supports all three repository resolution forms:

```bash
atlassian bitbucket pr list DEMO example-repo
atlassian bitbucket pr list -R DEMO/example-repo
atlassian bitbucket pr list
```

The first form matches the existing `pr diff`, `pr create`, `pr merge`, and
compatibility command grammar. The second form retains the `-R, --repo` selector.
The third form retains environment and local Git repository resolution.

`PROJECT_KEY` and `REPO_SLUG` are an optional pair. Supplying only one positional
argument is invalid. Supplying the positional pair together with `-R` is also
invalid, even when both forms identify the same repository. These validation
errors occur before authentication, repository discovery, or provider I/O.

## Native State Contract

`--state` defaults to `OPEN`. Accepted states are the Bitbucket Server states:

- `OPEN`
- `DECLINED`
- `MERGED`
- `ALL`

The same values are accepted in lowercase. Input is normalized to uppercase
before service and provider calls, so mixed case is harmless as well. GitHub-only
`closed` is rejected because Bitbucket represents that state as `DECLINED`.

The `state:` and `is:` search qualifiers follow the same accepted values and
normalization. A search state may replace the default `OPEN` query, while an
explicit non-default `--state` remains an additional predicate as it does today.

Human and JSON output retain the native resource states `OPEN`, `DECLINED`, and
`MERGED`. The presenter no longer converts `DECLINED` to `CLOSED`. The legacy
hidden `--output` path uses the same accepted input state set.

This state contract is an intentional deviation from `gh v2.96.0`, justified by
the Bitbucket-native command surface and upgrade compatibility.

## Pagination

Primary `pr list` pagination remains unchanged. It requests Bitbucket pages in
chunks of 100, advancing the server `start` offset until it has collected the
requested `--limit` after filtering or has exhausted the result set. The command
does not add a public `--start` option.

`pr browse` keeps its existing explicit `--start` and interactive next/previous
page behavior.

## Implementation Boundaries

The change is limited to:

- `bitbucket pr list` argument parsing and repository selection;
- PR list state parsing, service filtering, and output projection;
- matching README and parity documentation;
- unit, help, and live Bitbucket e2e coverage.

Other PR commands, generic `bitbucket api`, provider pagination, authentication,
and repository resolution precedence remain unchanged.

## Error Handling

Invalid grammar and states use the primary PR read exit policy and exit `1`:

- only one of `PROJECT_KEY` and `REPO_SLUG` is supplied;
- positional repository arguments are combined with `-R`;
- `--state` is not a Bitbucket-native value;
- a search qualifier contains a non-native state such as `state:closed`.

Errors must identify the conflicting or invalid input and happen before network
or filesystem discovery.

## Verification

Tests cover:

- both `PROJECT_KEY REPO_SLUG` and `-R PROJECT_KEY/REPO_SLUG` reaching the same
  repository and list service;
- repository inference when neither form is supplied;
- partial positional and mixed positional/`-R` rejection before I/O;
- uppercase, lowercase, and mixed-case native states;
- rejection of `closed` and other unsupported states;
- native state values in provider calls, search filtering, JSON, and human output;
- automatic multi-page reads remaining intact;
- live Bitbucket listing through both repository argument forms.

Final verification uses the repository virtualenv:

```bash
ruff format --check .
python -m pytest -q
ruff check README.md pyproject.toml src tests docs
ATLASSIAN_E2E=1 python -m pytest -q \
  tests/e2e/test_bitbucket_live.py::test_bitbucket_branch_and_pr_round_trip_live
```
