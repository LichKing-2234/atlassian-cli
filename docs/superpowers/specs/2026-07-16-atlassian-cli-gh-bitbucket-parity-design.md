# GitHub CLI Parity for Bitbucket Server Design

Status: Approved

Classification companion:
`docs/superpowers/specs/2026-07-16-atlassian-cli-gh-bitbucket-parity-matrix.md`

## Summary

Align the useful public `gh v2.96.0 pr` and `repo` command contract with
`atlassian bitbucket pr` and `atlassian bitbucket repo`. Command names, aliases,
usage, arguments, flags, defaults, prompts, repository and pull request
inference, human output, structured output, browser and pager behavior, and exit
codes match where Bitbucket Server 6.7.2 can support the same user intent.

Parity is the default, but it is not a license to reproduce GitHub history or to
make useful Bitbucket commands fail for non-essential metadata. Exact mappings,
documented deviations, hard blockers, and non-applicable GitHub-only surfaces are
classified separately. Backend calls use Bitbucket Server 6.7.2 REST or bounded
Git operations; the design does not introduce unbounded repository cloning just
to simulate provider metadata.

## Fixed Baselines

- GitHub CLI: `gh v2.96.0`, tag commit
  `b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0`.
- Verified macOS arm64 baseline binary SHA-256:
  `b1d6c442fde99ca27c04e1e74d624895abe37785f4a3e9e9b684bf7586ce4bc8`.
- Bitbucket: Atlassian Bitbucket Server `6.7.2`.
- Existing CLI: `atlassian-cli v0.1.19`, commit
  `2b5d8b2cedffda69fc963d83809186d9b5d62e79`.

The baselines are immutable. A later `gh` or Bitbucket version requires a new
matrix review rather than silently changing this contract.

The pinned `gh` release binary and source at the pinned commit are the mapped
behavior oracle. The binary provides observable grammar, output, prompt, and
exit fixtures; the source and its tests resolve service-dependent, TTY, hidden,
deprecated, and error-path behavior that cannot be isolated reliably from a
binary invocation. Generated help and the parity matrix are indexes and evidence
ledgers; neither may redefine behavior that disagrees with the oracle.

All oracle fixtures must be sanitized, checked into the contract harness, and
receive recorded review approval together with their atomic matrix rows before
implementation of the covered command begins. A fixture change is a contract
change and repeats that approval gate.

## Goals

- Expose the useful public `gh v2.96.0 pr` and `gh v2.96.0 repo` grammar that has
  an applicable Bitbucket Server meaning.
- Match each supported command's observable behavior even when implementation
  uses Bitbucket REST or Git instead of GitHub APIs.
- Make `-R, --repo`, repository URLs, pull request URLs, branch selectors,
  current-directory inference, and `repo set-default` consistent.
- Provide baseline-compatible `--json` behavior first, with command-specific
  field validation; add `--jq` and `--template` independently after the core
  workflows work without a formatter sidecar.
- Use `gh` exit codes for the parity command roots.
- Preserve existing Bitbucket workflows through explicit compatibility paths
  where they do not make the primary grammar ambiguous.
- Keep Bitbucket-specific `project`, `branch`, `commit`, explicit approval, raw
  output, and comment CRUD workflows available.
- Document and test every Bitbucket 6.7.2 limitation.

## Non-Goals

- Bitbucket Cloud or a Bitbucket Server version other than 6.7.2.
- Parity for Jira, Confluence, or `gh` command groups outside `pr` and `repo`.
- Adding GitHub-only concepts to Bitbucket through local metadata or hidden
  emulation.
- Byte-for-byte copying of GitHub wording where the product noun or URL must say
  Bitbucket. Grammar, defaults, behavior, output shape, and exits are normative.
- Removing existing Bitbucket-only command groups.
- Updating the parity baseline automatically when a new `gh` release appears.
- Copying source-hidden `repo credits` or `repo garden`, or deprecated `gh` flags
  that add no value to current `atlassian-cli` users.
- Registering GitHub-only commands and flags solely so that every invocation can
  fail on Bitbucket.
- Bulk-cloning repositories to synthesize `repo list` metadata such as language.

## Normative Status Model

Every normative atomic matrix row has exactly one status:

- `M` (`Exact`): the observable contract is reproduced through Bitbucket REST,
  bounded Git work, or both.
- `Dxx` (`Documented deviation`): the core user intent remains useful, but a
  non-critical observable detail differs. The deviation has explicit output,
  ordering, failure, and test requirements.
- `Bxx` (`Blocked`): a parser-visible command value or field requests a core
  semantic that Bitbucket Server 6.7.2 cannot provide safely or truthfully. It
  fails before mutation with evidence tied to the blocker code.
- `Nxx` (`Not applicable`): the surface is GitHub-only, source-hidden,
  deprecated without local compatibility value, or would require an unbounded
  implementation. It is recorded for scope accounting but is absent from the
  primary parser and help.

There is no `partial`, `candidate`, or `unverified` status. A value-dependent
surface is split into atomic rows. A command-level inventory is navigation only;
it cannot weaken flag, value, field, default, prompt, output, or exit rows. A
mixed or unresolved atomic row prevents implementation of that row, not unrelated
commands.

For a blocked row that remains in the parser:

1. The command or flag keeps the public baseline spelling, arity, and value type.
   It remains visible only when the surrounding Bitbucket workflow is useful and
   an explicit capability error is more actionable than omitting the value.
2. Parsing succeeds so the CLI can report the capability problem, not an unknown
   option error.
3. Static capability validation runs before read-only resolution when the
   blocker depends only on parsed input. Repository-dependent capability checks
   may perform the minimum authenticated read needed to classify the request,
   but every capability failure occurs before all Git or REST mutations.
4. The message is written to stderr in this form:

   ```text
   unsupported by Bitbucket Server 6.7.2: <capability>; required by gh v2.96.0 <surface>
   ```

5. The command exits `1` and performs no side effect.

`Dxx` rows must remain successful whenever the equivalent `gh` command would
succeed, unless the deviation evidence explicitly defines a narrower failure.
`Nxx` rows are documentation and coverage-ledger entries only: they are neither
registered as hidden commands nor accepted as parser options.

## Target Command Surface

### Pull Requests

- `checkout`, alias `co`
- `checks`
- `close`
- `comment`
- `create`, alias `new`
- `diff`
- `edit`
- `list`, alias `ls`
- `merge`
- `reopen`
- `revert`
- `review`
- `status`
- `update-branch`
- `view`

### Repositories

- `clone`
- `create`, alias `new`
- `delete`
- `deploy-key add|delete|list`, with alias `list -> ls`
- `edit`
- `fork`
- `gitignore list|view`, with alias `list -> ls`
- `license list|view`, with alias `list -> ls`
- `list`, alias `ls`
- `read-dir`
- `read-file`
- `rename`
- `set-default`
- `sync`
- `view`

### Explicit Scope Exclusions

- Source-hidden `repo credits` and `repo garden` are `N01`; they are not copied.
- Deprecated `gh` flags are `N02` unless the same spelling already protects a
  v0.1.19 workflow. Existing compatibility has priority over GitHub history.
- Public GitHub-only concepts that have no Bitbucket meaning are recorded as
  `N03` and omitted rather than filling help with flags that always fail.
- `repo list --language` and list-only Git-content-derived JSON fields are `N04`;
  a multi-repository clone/fetch fan-out is not an acceptable list implementation.

The companion matrix is the normative classification and evidence ledger at
atomic granularity. The pinned binary and source remain the exact-behavior oracle
for `M` rows and the comparison oracle for `Dxx`, `Bxx`, and `Nxx` rows.

## Selection Model

### Types

Parsing and resolution use separate types:

```text
RepositorySelector = ExplicitSlug | RepositoryUrl | CloneUrl | RemoteName | Inferred
PullRequestSelector = PullRequestId | PullRequestUrl | HeadBranch | CurrentBranch
ServerIdentity = configured base URL + normalized host + port + context path
RepositoryRef = ServerIdentity + project key + repository slug
PullRequestRef = RepositoryRef + numeric pull request ID
```

Selector parsing is pure. It validates syntax and detects conflicts without Git,
REST, credentials, or filesystem mutation. Resolution is an I/O operation that
uses small command-driven Git helpers and read-only provider calls.

### Repository Selector Syntax

The primary grammar accepts:

- `DEMO/example-repo`
- `[HOST]/DEMO/example-repo`
- a Bitbucket repository web URL
- an HTTPS clone URL ending in `/scm/DEMO/example-repo.git`
- an SSH clone URL
- a Git remote name where `repo set-default` accepts one

`[HOST]` must match the configured Bitbucket `ServerIdentity`. The CLI has one
active Bitbucket credential context, so another host exits `4` with an
authentication/configuration error rather than reusing credentials on that host.

### Repository Resolution Precedence

After a command's own grammar has selected a repository input, the common finder
uses this order where that command invokes it:

1. Repository embedded in a pull request URL.
2. Explicit `-R, --repo` or explicit repository argument.
3. `ATLASSIAN_BITBUCKET_REPO`.
4. The remote selected by `repo set-default` in local Git config.
5. The current branch's upstream remote.
6. `origin` when it resolves to the configured Bitbucket server.
7. The only remaining remote that resolves to the configured server.
8. A TTY picker when several matching remotes remain.

Non-TTY ambiguity exits `1` and lists the matching remote names. No match exits
`1` and requests `-R`. A valid pull request URL is authoritative for commands
whose pinned finder accepts it and overrides the base repository selected by
`-R`, `ATLASSIAN_BITBUCKET_REPO`, set-default, or remotes.

This is not a universal parser conflict rule. Positional repositories, `-R`, PR
URLs, remote names, and inferred repositories are accepted and combined only on
the commands where the oracle does so. A shared selector helper must not reject
a combination that the pinned command accepts or add a repository form to a
command that does not accept it. The atomic matrix and parser fixtures own these
command-specific decisions.

The local default marks one remote with `remote.<name>.atlassian-resolved=base`.
Storing the remote rather than a literal slug keeps renames and URL changes
coherent. `repo set-default` first parses an explicit repository selector and
then, if that fails, an exact remote name. The selected repository must come from
the current remotes or their Bitbucket fork network. `--view` prints the canonical
`DEMO/example-repo`; `--unset` removes the marker idempotently. With no argument,
a TTY picker lists matching remotes, while the oracle's non-TTY guard is copied
exactly.

The argument, `--view`, and `--unset` are not mutually exclusive. Argument
parsing and validation runs first; operation precedence is `--view`, then
`--unset`, then set/pick. Thus accepted combinations preserve the oracle's
precedence rather than producing an invented conflict error.

### Pull Request Resolution

- A numeric ID uses the resolved repository.
- A pull request URL supplies both repository and ID and overrides other
  repository sources.
- A branch accepts `branch` and `PROJECT:branch`. Matching follows the baseline
  finder: exact source repository and ref matches are ranked with open pull
  requests first and newest creation time next. The first full match is selected;
  zero matches exit `1`.
- An omitted selector resolves the current branch where the command's pinned
  finder permits it.
- With `-R` and no PR selector, registered `checks`, `comment`, `diff`, `merge`,
  `review`, `update-branch`, and `view` exit `1` with the oracle's
  argument-required error before current-branch inference. The oracle applies the
  same guard to N03 `ready`, but that command is not registered.
- `edit -R` is an exception to that guard and still attempts current-branch
  inference when its PR selector is omitted.
- `checkout` without a selector presents the 10 most recent open pull requests
  in a TTY and exits `1` in non-TTY mode. Supplying `-R` changes the repository
  used by that picker; it does not require a selector in TTY mode.
- `status -R` does not parse the current branch and omits the current-branch
  group while rendering the other status groups for the selected repository.
- Registered `close`, `reopen`, and `revert` require a selector exactly as shown
  in the matrix. N03 `lock` and `unlock` are recorded but not registered.
- A detached HEAD cannot supply `CurrentBranch`; the exact result remains
  command-specific because commands such as `status` tolerate its absence.

## Input and Interactive Behavior

- Body precedence is command-specific. `pr create` accepts `--body` together
  with `--body-file`; file content wins and marks the body provided. Its
  `--template` conflicts with either source. `pr comment`, `pr edit`, `pr merge`,
  `pr review`, and `pr revert` reject simultaneous `--body` and `--body-file`
  before reading the file or performing network I/O.
- `--body-file -` reads stdin exactly once.
- Parser dependencies and exclusions are copied per command, not inferred from
  a common flag name. The atomic grammar covers all conditionals in `pr create`,
  `comment`, `edit`, `list`, `merge`, and `review`, and `repo create`, `clone`,
  `list`, `edit`, `fork`, and `read-file`. This includes fill/editor/web/template
  combinations, comment last-item dependencies, review action/body rules,
  merge strategy, visibility and source/template rules,
  `--` Git argument boundaries, topic/settings dependencies, and output-mode
  exclusions. Parser validation and its exact message precede I/O unless the
  oracle intentionally resolves context first.
- Editor precedence is `ATLASSIAN_EDITOR`, `GIT_EDITOR`, `VISUAL`, then `EDITOR`.
- Browser precedence is `ATLASSIAN_BROWSER`, then `BROWSER`, then the platform
  default.
- Pager precedence is `ATLASSIAN_PAGER`, then `PAGER`, then the platform default.
- `CanPrompt` is true only when stdin and stdout are TTYs and prompting has not
  been disabled. `ATLASSIAN_PROMPT_DISABLED` disables prompting when present
  with any value; otherwise the product configuration does so. Stderr TTY state
  is irrelevant. `ATLASSIAN_FORCE_TTY`, when supported, affects stdout TTY
  detection. A missing value that `gh` would prompt for exits `1` in
  non-interactive mode with the matching usage text.

The product-prefixed environment variables are intentional `D01` deviations.
The CLI does not read `GH_REPO`, `GH_EDITOR`, `GH_BROWSER`, `GH_PAGER`,
`GH_PROMPT_DISABLED`, or `GH_FORCE_TTY`; doing so would let configuration for an
unrelated GitHub client silently steer Bitbucket operations.

- Negative prompt answers are not assigned one global exit. `pr create`,
  `pr merge`, and `repo create` explicit cancellation returns cancellation exit
  `2`; `pr review` declining `Submit?` and `repo rename`
  declining confirmation return success `0` with no mutation; `pr comment`
  declining submit/edit returns the ordinary `Discarding...` error and declining
  `--delete-last` returns `deletion not confirmed`, both exit `1`. Repository
  delete uses the oracle's typed-name prompt and interrupt behavior. Every prompt
  branch has its own approved fixture for output, side effects, and exit.
- `repo read-file` refuses terminal escape sequences for terminal and piped
  output unless `--allow-escape-sequences` is supplied. File output preserves raw
  bytes and follows the direct-write contract below.

## Existing Command Compatibility

The primary `pr` and `repo` help output contains the applicable public `gh`
surface plus documented Bitbucket extensions. Compatibility commands and inputs
remain callable without redefining the primary grammar.

The non-conflicting compatibility commands remain independent hidden commands:

- `pr get PROJECT REPO ID`
- `pr build-status PROJECT REPO ID`
- `pr approve PROJECT REPO ID`
- `pr unapprove PROJECT REPO ID`
- `repo get PROJECT REPO`

They keep their v0.1.19 arguments, `--output`, renderer, and exit policy.

Old forms that collide with the same primary command grammar are breaking
migrations rather than invisible parser extensions:

- `pr list PROJECT REPO ...` -> `pr list -R PROJECT/REPO ...`
- `pr diff PROJECT REPO ID ...` -> `pr diff ID -R PROJECT/REPO ...`
- `pr create PROJECT REPO ...` -> `pr create -R PROJECT/REPO ...`
- `pr merge PROJECT REPO ID ...` -> `pr merge ID -R PROJECT/REPO ...`
- `repo list --project PROJECT ...` -> `repo list PROJECT ...`
- the existing `repo create --project ... --name ...` form -> the primary
  `repo create PROJECT/example-repo ...` form

Existing comment CRUD moves from the conflicting singular group to the explicit
Bitbucket extension `pr comments list|get|add|reply|edit|delete`. The primary
`pr comment [PR]` is never double-parsed as a nested group.

Behavioral migrations are explicit:

- Primary `pr list` uses the `gh` line-oriented list, not the existing full-screen
  interactive browser. The current browser moves to the documented Bitbucket
  extension `pr browse PROJECT REPO [--state ...] [--start ...] [--limit ...]`.
  It keeps the v0.1.19 browser: use it when interactive output is available, and
  fall back to the old static Markdown list when the browser cannot initialize or
  output is non-interactive. `pr list --web` retains the pinned behavior of
  opening the repository's pull request list in a web browser.
- Primary `pr diff` writes only diff or patch content. It no longer includes pull
  request detail around the diff.
- Primary `pr checks` evaluates the head commit. Hidden `build-status` preserves
  the existing all-commit default and `--latest-only` option.
- Primary `view`, `list`, and mutation commands use `gh` human output by default.
  Existing per-command `--output` options remain as hidden, deprecated
  compatibility inputs and select the v0.1.19 renderer. New parity commands do
  not gain this option, and it is not used as a root-level global override.
- `repo read-file -o, --output` always means a destination path. Legacy structured
  output for this new command does not exist; use `--json` for structured output.
  The destination option is never interpreted as a legacy structured format.
- Primary `bitbucket pr` and `bitbucket repo` commands adopt `gh` exit codes.
  Hidden compatibility commands, Jira, Confluence, and other Bitbucket groups
  keep the existing exit policy.

## Output Contract

### Human Output

- Primary command output follows `gh v2.96.0` layout, headings, ordering,
  pagination summaries, color policy, prompts, and stdout/stderr split with
  product nouns and URLs changed to Bitbucket.
- `pr list` defaults to open pull requests and limit 30, fetching across
  Bitbucket pages until the limit is satisfied.
- `pr diff` defaults to raw diff text and `--color auto`.
- `pr checks` reports head-commit build statuses and exits `8` while any status is
  pending.
- `repo view` includes repository metadata and README content.
- `--web` opens the equivalent Bitbucket web page and does not render the normal
  terminal detail.
- `repo list` remains useful even though Bitbucket 6.7.2 has no `pushedAt` or
  `createdAt`. Results use stable `nameWithOwner` ascending order and the human
  `UPDATED` cell is `-` (`D03`). The command never substitutes local commit time
  for server push time. Explicit JSON requests for unavailable lifecycle fields
  remain blocked by `B23`.
- A non-empty `repo deploy-key list` renders `-` in the default human `CREATED AT`
  column (`D04`) because the access-key payload has no creation timestamp. An
  explicit JSON request for `createdAt` remains `B23`. The empty result remains
  exact: when stdout is a TTY it writes
  `no deploy keys found in DEMO/example-repo` to stderr and exits `0`; non-TTY
  empty output also exits `0`.

Golden output fixtures are sanitized and versioned with the parity matrix. No
presenter implementation starts until its exact stdout, stderr, TTY, color,
pager, and exit fixtures have passed the recorded oracle-fixture approval gate.

### JSON, jq, and Go Templates

- `--json` accepts the command-specific M/D/B subset of the fields listed by
  `gh v2.96.0`; N fields are omitted from the accepted field list.
- `--json` without a value prints the following line and the sorted field list to
  stderr, performs no network call, and exits `1`:

  ```text
  Specify one or more comma-separated fields for `--json`:
  ```
- An unknown field exits `1` before network I/O.
- A `Bxx` field is accepted by the parser but exits `1` with the capability error
  before network I/O. An `Nxx` field is not in that command's allowed field list.
- `--jq` and `--template` require `--json`. Supplying both is valid: jq output
  takes precedence and the template is ignored, matching `gh v2.96.0`.
- Non-TTY JSON is compact JSON followed by one newline. TTY JSON is pretty
  printed with the baseline color policy. Template output does not gain an
  implicit newline.
- JSON property names, null handling, array/object shape, jq raw output, template
  whitespace, color, tabular helpers, and time formatting follow the baseline.
- `repo read-dir --json` always emits an object envelope with structural `id`,
  `gitSHA`, and `entries` properties. Requested fields select properties within
  each entry only. `modeOctal` is six-digit octal; `nameRaw` and `pathRaw` retain
  the oracle encoding; and a non-null `submodule` object has `gitUrl`, `branch`,
  and `subprojectCommitOid`.
- `repo read-file --json content` emits base64 content and reports `encoding` as
  `base64`, including when a large file required a separate raw-content fetch.
  `--json` and `--output` are mutually exclusive.

Baseline-compatible `--json` serialization is implemented in Python and does not
depend on another runtime. Exact `--jq` and `--template` compatibility is a later,
independent capability. The preferred implementation is a bundled
`atlassian-gh-format` helper built with the baseline formatter dependencies:

- `github.com/itchyny/gojq v0.12.17`
- `github.com/Masterminds/sprig/v3 v3.3.0`
- compatible helpers from `github.com/cli/go-gh/v2 v2.13.0`

The optional helper implements `autocolor`, `color`, `join`, `pluck`, `tablerow`,
`tablerender`, `timeago`, `timefmt`, `truncate`, and `hyperlink`. It reads JSON on
stdin and never receives credentials. Release builds compile and bundle it for
Linux amd64, macOS arm64, macOS amd64, and Windows amd64. Python packages become
platform wheels for those targets; source builds require Go. This Python, Rust,
and Go release cost must be justified and verified in its own phase. Until then,
commands expose base `--json` without `--jq` or `--template`. Contract tests run
the formatter corpus through the helper and `gh v2.96.0` only in that phase.

### Exit Codes

Within primary `bitbucket pr` and `bitbucket repo` commands:

- `0`: success
- `1`: validation, capability, not found, conflict, Git, network, server, or
  formatting failure
- `2`: only prompt branches and interrupts classified by the oracle as user
  cancellation; a negative answer that returns success or an ordinary error
  keeps that branch's `0` or `1`
- `4`: a command requires authentication but no credential is configured
- `8`: `pr checks` has pending checks

Errors write to stderr. Machine-readable success output never receives notices or
warnings on stdout.

## Architecture

### Modules

`products/bitbucket/gh_compat/selectors.py`

- Defines selector and resolved reference types.
- Parses selectors and detects explicit conflicts without I/O.

`products/bitbucket/gh_compat/repository_context.py`

- Resolves selectors through Git remotes, local defaults, and read-only REST.
- Owns the precedence table and ambiguity errors.

`products/bitbucket/gh_compat/capabilities.py`

- Stores blocker codes and performs command, flag, value, and JSON-field
  preflight checks.

`products/bitbucket/services/`

- Extends existing services one workflow at a time. A command receives only the
  Git operations it needs; there is no up-front all-purpose Git gateway.

`products/bitbucket/providers/server.py`

- Owns Bitbucket Server 6.7.2 HTTP paths, payloads, pagination, and error
  translation.

`products/bitbucket/gh_compat/output/`

- Owns canonical resource projections, human presenters, JSON field selection,
  and the formatter-helper boundary.
- Does not decide process exits.

`products/bitbucket/gh_compat/exit_policy.py`

- Maps typed failures to the parity exit codes only for `bitbucket pr` and
  `bitbucket repo`.

### Typer Grammar

`-R, --repo` is declared through a reusable annotated option on every applicable
command so it works after the subcommand exactly as shown by `gh`; it is not only
a parent-group option. The option helper supplies spelling and type only;
command-specific selector and flag-relation validation remains on each command.
`M`, `Dxx`, and parser-visible `Bxx` options are real parser inputs. `Nxx` options
and commands are not registered. Existing compatibility inputs may be registered
as hidden/deprecated, but source-hidden or deprecated `gh` history is not copied.

### Data Flow

```text
argv
  -> Typer parse: arity, enum, and command-specific flag relations
  -> static capability preflight from parsed input
  -> read-only repository, pull request, Git, and settings resolution
  -> repository-dependent dynamic capability preflight
  -> service orchestration
  -> first Bitbucket or Git mutation
  -> canonical projection
  -> human presenter or available JSON/jq/template formatter
  -> gh exit policy
```

This order is normative. Parser errors win over capability errors. Static
blockers do not perform authenticated reads. A dynamic blocker, such as whether
a requested merge method equals the repository's effective Bitbucket merge
method, may authenticate and read context but still performs zero mutation.

## Bitbucket 6.7.2 Capability Basis

Supported mappings use these official resources:

- Pull request CRUD, comments, participants, decline, reopen, approve, merge,
  diffs, commits, activities, dashboard queries, repository CRUD, forks,
  branches, browse/raw content, labels, README, and license:
  <https://docs.atlassian.com/bitbucket-server/rest/6.7.2/bitbucket-rest.html>
- Build statuses:
  <https://docs.atlassian.com/bitbucket-server/rest/6.7.2/bitbucket-build-rest.html>
- Pull request rebase:
  <https://docs.atlassian.com/bitbucket-server/rest/6.7.2/bitbucket-git-rest.html>
- Repository access keys:
  <https://docs.atlassian.com/bitbucket-server/rest/6.7.2/bitbucket-ssh-rest.html>

Blocker evidence uses the complete 6.7.2 REST/WADL resource set and the absence
of the concept from repository or pull request representations. The matrix lists
each blocker code and why Git cannot reproduce it without inventing persistent
state or changing the requested meaning.

### Required Atomic Capability Decisions

- `pr merge` never silently uses the Bitbucket server default when no method was
  supplied. Outside GitHub's merge-queue branch, the pinned non-TTY error is
  `--merge, --rebase, or --squash required when not running interactively`; the
  TTY path prompts for a method. Bitbucket 6.7.2 has no merge queue.
- A requested `--merge`, `--rebase`, or `--squash` method is mapped only when it
  equals the repository's read-only resolved effective Bitbucket merge method.
  Other requested methods are B12 after dynamic capability preflight. Temporarily
  changing repository merge settings is not equivalent: it requires repository-
  administration permission beyond the merge itself, the setting is shared,
  races with other users and merges, affects operations outside this invocation,
  and cannot be rolled back transactionally without possible residue. A local Git
  merge/rebase/squash is also not equivalent because pushing it bypasses
  Bitbucket PR merge checks, hooks, server-recorded actor, optimistic PR version,
  audit/activity, the server `MERGED` transition, and the atomic merge transaction.
- B13 merge author, subject, and body controls cannot be rescued by local Git.
  The 6.7.2 merge endpoint has no per-invocation fields for them, repository
  settings do not provide them, and pushing a locally authored commit bypasses
  the same checks, hooks, actor/version, audit/activity, state transition, and
  atomic server PR merge contract.
- `repo create` default and interactive paths create the Bitbucket repository
  successfully (`D02`). The result has no GitHub issues or wiki because Server
  6.7.2 has neither feature. An explicit public flag value that requests enabling
  either feature is B19; deprecated inverse flags are N02 and are not copied.
- `repo create --team` maps the pinned team write grant to a Bitbucket group
  `REPO_WRITE` grant. The group is resolved read-only before creation. If the
  post-create permission grant fails, the service deletes the newly created
  repository; a failed deletion reports both failures and the residue identifier.
  The naming difference between a GitHub team and a Bitbucket group is not itself
  a blocker when the write-grant behavior can be preserved.
- Bitbucket repository labels reject names shorter than three characters.
  Therefore `repo edit --add-topic` with a one- or two-character topic is blocked
  by value; removing such a topic is a mapped no-op because it cannot exist, and
  `repo list --topic` for such a value maps to an empty result. These value classes
  are separate atomic rows.
- `pr checks` projects Bitbucket build statuses as baseline `StatusContext`
  records. Its checks JSON therefore uses zero `startedAt`/`completedAt` values
  and empty `event`/`workflow` strings, while PR `statusCheckRollup` exports the
  build `dateAdded` as the status context's `startedAt`.
- PR JSON `reviews` and `latestReviews` are B30. Reviewer status, review activity,
  and comments are separate records and cannot be joined unambiguously into the
  baseline review object's body, state, association, reviewed commit, reactions,
  stable ID, and URL. PR JSON `mergeCommit` is B31 because the 6.7.2 PR, merge
  response, and activity contracts expose no stable merge-commit identity.
- `pr review --approve|--request-changes` is `D05`, not `M`: Bitbucket stores the
  optional comment and participant status as separate operations. Compensation
  reduces residue but cannot make the operation or resulting record atomic.
- `repo fork --default-branch-only` is B33. The fork endpoint has no atomic
  default-branch-only parameter; creating a full fork and deleting refs afterward
  exposes an observably different intermediate state and may leave residue.
- Repository JSON uses provider-accurate constants for absent state when the
  baseline field can still be expressed: false feature/archive/template/mirror
  booleans, zero stars, null object/time fields, and empty exported URL strings.
  Collections and viewer metadata that require real membership or identity data
  remain blocked. For the same reason, an explicitly empty `--homepage` on
  `repo create` or `repo edit` is a mapped no-op/clear; only a non-empty homepage
  value is B16.
- Repository JSON field `assignableUsers` is B32. PR participants are not an
  assignable-user set, while permission user/group endpoints require elevated
  access and do not reconstruct inherited and global permission membership.
- Missing repository timestamps and access-key `createdAt` block only explicit
  JSON field requests. Default human list modes use D03 and D04 placeholders
  instead of making the entire command unusable.
- Repository field sets are command-specific. `repo view` may derive
  `languages` and `primaryLanguage` from one bounded repository fetch. `repo list`
  does not expose language filtering or Git-content-derived fields because doing
  so would require a clone/fetch fan-out across every candidate repository (N04).

## Multi-Step Operations and Error Handling

- Validation follows the normative data-flow order: baseline parser/arity/enum
  and flag relations, static capability, read-only resolution, repository-
  dependent dynamic capability, then mutation. Every blocker precedes mutation,
  but a dynamic blocker may require authenticated reads.
- `review --request-changes --body ...` creates the comment, changes the current
  participant to `NEEDS_WORK`, and deletes the comment if the status update
  fails. A failed rollback reports the comment ID on stderr and exits `1`. This
  is the documented D05 non-atomic path, not an exact review-object mapping.
- `review --approve --body ...` uses the same compensation rule around approval.
- `close --comment` creates the comment before declining the pull request. If the
  decline fails, the successfully created comment remains, matching the baseline;
  the CLI does not compensate by deleting it. `reopen --comment` has the same
  comment-first order and leaves the comment when reopening later fails.
- `--delete-branch` runs only after the close or merge succeeds. A branch deletion
  failure reports the successful pull request mutation and exits `1`.
- `pr revert`, merge-style `pr update-branch`, remote `repo sync`, and repository
  initialization use a mode-0700 temporary Git directory. They leave the user's
  worktree unchanged and always attempt cleanup.
- Non-fast-forward update and sync fail unless the baseline flag explicitly
  permits force or rebase.
- Repository delete follows `gh` confirmation rules: without an explicit
  repository, `--yes` is ignored and confirmation is always required.
- Pagination guards against repeated cursors and stops at the requested limit.
- HTTP 401 and 403 are runtime failures and map to `1`. Exit `4` is reserved for
  the preflight case where a command needs authentication and none is configured.
- HTTP 404, 409, 429, and 5xx responses retain the server message on stderr but
  map to exit `1`.

## Credential and Filesystem Safety

- Credentials never appear in Git subprocess arguments, logs, exceptions, or
  formatter input.
- HTTPS Git authentication uses environment-backed Git configuration or a
  mode-0700 `GIT_ASKPASS` helper that is deleted with the temporary directory.
- SSH uses the user's normal SSH agent and configuration.
- Temporary clones and body recovery files use mode 0600 files under mode 0700
  directories.
- `repo read-file --output` copies the pinned direct-write behavior rather than
  promising atomic replacement. It uses `lstat`, refuses a symlink at either the
  supplied output path or final destination, treats an existing directory or a
  trailing separator as a directory and appends the remote basename, creates
  missing parents with mode 0755, and calls the direct file write with mode 0644.
  An existing destination fails unless `--clobber` is set; clobber truncates and
  writes directly, so a write failure can leave a partial file.
- Capability and validation failures have zero Git and REST mutation calls,
  asserted by tests.

## Implementation Phases

Issue #32 remains the epic. Delivery is vertical: each PR completes a small
command or workflow through parser, provider/service, output, docs, unit tests,
and affected live e2e. Shared code is extracted only after two real workflows
need it.

1. **Contract and selector foundation**
   - Commit the sanitized public-surface fixtures needed by the first workflows,
     the status/evidence validator, selector parsing, repository resolution, and
     local exit policy. Do not build the complete Git or formatter layer here.
2. **`pr view` and `pr list`**
   - Deliver human output, base `--json`, selection/inference, pagination, the
     D01 environment namespace, and the preserved `pr browse` extension.
3. **`repo view` and `repo clone`**
   - Deliver repository selection, README/view projection, bounded single-repo
     language derivation, clone URL behavior, and only the Git operations these
     commands require.
4. **One mutation workflow**
   - Choose one low-risk mutation such as `pr comment`, and complete validation,
     preflight, mutation ordering, cleanup, docs, and live e2e before creating a
     broader mutation abstraction.
5. **Command-by-command expansion**
   - Add one command or tightly coupled workflow per PR. Each PR updates only its
     relevant matrix rows and fixtures. D/B/N classifications are implemented as
     encountered; N rows never create parser stubs.
6. **Optional `--jq` and `--template`**
   - Add the Go helper, platform wheels, release packaging, and formatter corpus
     only after base `--json` workflows are stable. This phase may be postponed
     without blocking command delivery.
7. **Compatibility and completion audit**
   - Finish migration docs, live coverage, release-artifact smoke tests, and the
     requirement-by-requirement audit after the command set is complete.

A later PR may refine a row when new oracle or server evidence appears, but it
must update the design, matrix, fixture, and tests together. Approval of unrelated
future rows is not a prerequisite for shipping a completed vertical workflow.

## Testing

### Contract Tests

- Parse `gh v2.96.0` public reference output and assert every public command,
  alias, usage, argument, and flag is classified. Audit source-hidden and
  deprecated surfaces into N01/N02 without registering them.
- Compare Typer help grammar with the sanitized M/D/B public contract and assert
  that N surfaces are absent.
- Test omitted-argument behavior separately for every registered command;
  `checkout` retains its interactive-picker exception, `edit -R` its
  branch-inference exception, and the seven registered `-R` guards their argument
  error. The eighth oracle guard, `ready`, is covered by the N03 inventory test.
- Test every command-specific mutual exclusion, dependency, parser error, prompt
  availability condition, and negative prompt branch against approved fixtures.
- Test `--json` missing values, unknown fields, blocked fields, per-command field
  sets, serialization, and exits against the baseline binary. Add jq, template,
  helper, color, time, and whitespace fixtures only with the optional formatter
  phase.

### Unit and Integration Tests

- Selector syntax, URL parsing, precedence, host validation, conflicts,
  ambiguity, detached HEAD, branch lookup, and current-branch inference.
- Compatibility commands, `pr browse`, hidden/deprecated existing `--output`, and
  rejection of removed conflicting legacy positionals.
- Capability preflight and zero mutation side effects for every B row; exact
  documented behavior for every D row; parser/help absence for every N row.
- Temporary Git workflows, cleanup, credential redaction, fast-forward checks,
  force/rebase behavior, branch deletion, and submodules.
- REST pagination, model projection, value-level blockers, compensation, and
  partial-failure messages.
- `repo read-dir` TTY table, non-TTY TSV, empty/error cases, six-digit modes, raw
  names/paths, submodules, and the structural `id`/`gitSHA`/`entries` JSON envelope.
- `repo read-file` regular-file enforcement, directory/symlink/submodule errors,
  TTY pager, pipe, empty, binary, escape-sequence, base64 JSON, `--json`/`--output`
  conflict, direct output, directory creation, symlink refusal, and clobber modes.
- Formatter helper smoke tests in wheel and standalone bundles on every release
  target, only after the optional formatter phase exists.

### Live E2E

Every new command is added to `tests/e2e/coverage_manifest.py`. Feature-specific
tests run with `ATLASSIAN_E2E=1` against the configured Bitbucket Server 6.7.2
instance. Tests use temporary neutral resources, register cleanup before each
mutation, and report residue identifiers if cleanup fails.

Blocked values receive parser and zero-side-effect tests; N rows receive parser
absence tests and do not need a destructive live call. REST-backed mappings,
including participant `NEEDS_WORK`,
merge strategies, rebase, access keys, repository labels, browse/raw content,
and temporary Git authentication, require live coverage before being called
verified.

## Documentation

- README leads with the `gh`-compatible command forms.
- A user-facing parity page renders the matrix without internal implementation
  columns.
- Migration documentation lists compatibility commands, the move of the old
  full-screen browser to `pr browse`, hidden/deprecated existing `--output`
  behavior, changed defaults, and exit-code changes.
- Blocked surfaces name Bitbucket Server 6.7.2 and link to their blocker code.
- Examples use only the repository-approved neutral placeholder set.

## Acceptance Criteria

- The matrix validator accounts for every public `gh v2.96.0 pr` and `repo`
  command, alias, argument, and flag as M, Dxx, Bxx, or Nxx. Source-hidden and
  deprecated surfaces are accounted for as N01/N02, not copied automatically.
- Every implemented command, flag, restricted value, output atom, and JSON field
  has a closed evidence reference and no mixed status.
- Primary help exposes the applicable parity surface, including `read-dir` and
  `read-file`; N rows are absent. Existing compatibility commands and options
  follow their documented visibility, and `pr browse` keeps the current browser.
- Supported commands match baseline selection, prompts, defaults, stdout,
  stderr, JSON, browser/pager behavior, and exits for equivalent fixtures; jq
  and templates join this criterion only when the optional formatter phase ships.
- B surfaces exit `1`, emit the documented capability error, and make zero
  mutation calls; D surfaces remain usable with their documented output; N
  surfaces are rejected as unknown parser inputs.
- Approved oracle fixtures and atomic classifications exist before implementation
  starts, and the validator reports no mixed or unresolved atomic status.
- Non-conflicting v0.1.19 compatibility commands, `pr browse`, and existing hidden
  `--output` paths continue to parse. Conflicting positional, comment CRUD, and
  exit-code migrations are documented.
- `tests/e2e/coverage_manifest.py`, README, parity docs, and feature-specific live
  e2e coverage are updated with every implementation phase.
- Live tests pass against Bitbucket Server 6.7.2 for all mapped REST and Git
  workflows.
- When the formatter phase ships, release artifacts on Linux amd64, macOS arm64,
  macOS amd64, and Windows amd64 include and exercise the helper. It is not an
  acceptance dependency for base `--json` command phases.
- Repository verification passes with:

  ```text
  .venv/bin/ruff format --check .
  .venv/bin/python -m pytest -q
  .venv/bin/ruff check README.md pyproject.toml src tests docs
  ```
