# gh v2.96.0 to Bitbucket Server 6.7.2 Parity Matrix

This matrix is normative for the design in
`2026-07-16-atlassian-cli-gh-bitbucket-parity-design.md`.

## Baseline and Notation

- `gh`: `v2.96.0`, commit `b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0`
- Bitbucket: Server `6.7.2`
- `M`: exact mapping; the observable command behavior matches `gh`
- `Dxx`: documented deviation with usable core behavior
- `Bxx`: parser-visible hard blocker backed by the blocker table
- `Nxx`: not applicable; recorded here but absent from primary parser/help

A B row fails preflight with exit `1` and zero mutation side effects. A D row
remains usable with the exact deviation in the evidence table. An N row is not a
hidden failure stub: it is not registered. A row marked M is not partial.

Command inventory tables are non-normative navigation aids and intentionally
have no status column. Every table that has a `Status` column is normative and
atomic: its status cell contains exactly one `M`, `Dxx`, `Bxx`, or `Nxx`. A
command summary never weakens the atomic command, flag, value, parser,
output-mode, or JSON-field rows below it.

## Common Contract

| Surface | gh v2.96.0 contract | Bitbucket mapping | Status |
|---|---|---|---|
| Pull request selector | Number, URL, or head branch; optional only where usage shows brackets | `PullRequestSelector`; URL is authoritative; number and branch use repository resolution | M |
| Full repository selector | `OWNER/REPO`, `[HOST/]OWNER/REPO`, HTTPS/SSH URL, or clone URL where the command accepts a repository | `OWNER` maps to project key; personal projects keep `~example-user`; host must match the configured server | M |
| Bare repository name on applicable `repo clone`, `repo delete`, and `repo view` | Prefix the authenticated user's owner | Resolve the current Bitbucket user and prefix the personal project `~example-user` | M |
| Bare new-repository name on `repo create` | Create under the authenticated user's owner | Create under the current user's personal project `~example-user` | M |
| Bare `--template` repository on `repo create` | Prefix the authenticated user's owner | Resolve the source from the current user's personal project | M |
| Bare repository name on applicable commands other than `repo create`, `repo clone`, `repo delete`, and `repo view` | Reject unless the command gives the token another documented meaning, such as a remote name for `repo set-default` | Same usage failure before I/O | M |
| Bare repository name on source-hidden `repo garden` | Prefix the authenticated user's owner | Not registered with the N01 command | N01 |
| Bare repository name on `repo archive` and `repo unarchive` | Prefix the authenticated user's owner | Not registered with the N03 commands | N03 |
| Explicit URL passed to `repo clone` | Preserve the supplied HTTPS/SSH protocol; discard path components after the repository plus query and fragment | Parse the canonical project/repository but retain the explicit clone protocol | M |
| `repo clone` selector ending in `.wiki` | Resolve the base repository, require its wiki, and clone `<repo>.wiki.git` | GitHub-only wiki repository form is not registered | N03 |
| `-R, --repo` on registered `pr` commands | Available on every public baseline `pr` subcommand | Reusable option on every registered command; N03 commands are accounted for separately | M |
| `-R, --repo` on `repo` | Available only on public `autolink *`, `deploy-key *`, `read-dir`, `read-file`, and `rename` | Register it on `deploy-key *`, `read-dir`, `read-file`, and `rename`; the N03 autolink group is absent | M |
| Repository environment override | `gh` uses `GH_REPO` below explicit URL/`-R` and above local default/remotes | Use `ATLASSIAN_BITBUCKET_REPO`; do not read `GH_REPO` | D01 |
| Omitted optional PR selector with `-R` on registered `checks`, `comment`, `diff`, `merge`, `review`, `update-branch`, and `view` | Explicit PR selector required | Exit `1` before local branch inference | M |
| Omitted optional PR selector with `-R` on `ready` | Explicit PR selector required in the oracle | Not registered with the N03 command | N03 |
| `--json fields` parser | Select command-specific fields | Canonical Bitbucket projections use the exact field names below; each requested field is classified separately | M |
| Missing `--json` value | Sorted fields to stderr; exit `1`; no network | Same | M |
| `-q, --jq expression` | Requires `--json`; gojq semantics | Optional formatter phase using gojq v0.12.17 | M |
| `-t, --template string` | Requires `--json`; Go template, Sprig, and gh helpers | Optional formatter phase using baseline Go dependencies | M |
| Both jq and template | Valid; jq takes precedence | Same | M |
| Common exits | Success `0`, failure `1`, cancel `2`, missing auth `4` | Local `GhExitPolicy` for primary parity commands | M |

## Pull Request Command Inventory

This table is a non-normative summary. Availability is classified in the next
table, and flags, values, parser rules, output modes, and fields are classified
independently.

| Command and usage | Alias | Default and observable behavior | Bitbucket implementation summary |
|---|---|---|---|
| `pr checkout [<number> \| <url> \| <branch>]` | `co` | No selector: TTY picker with 10 newest open PRs; non-TTY exit `1` | Resolve source ref/repository; Git fetch and checkout |
| `pr checks [<number> \| <url> \| <branch>]` | - | Head commit only; failed `1`, pending `8`, pass `0`; JSON success exits `0` | Build-status REST for `fromRef.latestCommit`; local polling |
| `pr close {<number> \| <url> \| <branch>}` | - | Required selector; comment then close; optional branch deletion; already closed `0` | Comment, decline with version, then Git/branch delete; a successful comment remains if decline fails |
| `pr comment [<number> \| <url> \| <branch>]` | - | Current-branch inference; prompt/editor without body; last-comment operations target current user | Activities/comments REST |
| `pr create` | `new` | Current branch by default; prompt/push/fork; base precedence; print created PR URL | Git plus create/update PR REST |
| `pr diff [<number> \| <url> \| <branch>]` | - | Current-branch inference; raw diff by default | `.diff`, `.patch`, changes REST, and local filtering |
| `pr edit [<number> \| <url> \| <branch>]` | - | Current-branch inference; interactive prompt when no flags in TTY | Fetch-modify-PUT PR and reviewer endpoints |
| `pr list` | `ls` | No PR argument; open, newest, limit 30; static output; empty is success | Pull-request paging and client-side equivalent filters |
| `pr lock {<number> \| <url>}` | - | Lock conversation | N03; not registered because Bitbucket has no conversation-lock concept |
| `pr merge [<number> \| <url> \| <branch>]` | - | Current-branch inference; conditional method prompt/validation described below | Mergeability, merge settings, and merge REST |
| `pr ready [<number> \| <url> \| <branch>]` | - | Ready by default; `--undo` returns to draft | N03; not registered because Bitbucket has no draft state |
| `pr reopen {<number> \| <url> \| <branch>}` | - | Required selector; comment then reopen; already open `0` | Comment then reopen with optimistic version; a successful comment remains if reopen fails |
| `pr revert {<number> \| <url> \| <branch>}` | - | Required merged PR; creates and prints a revert PR | Mode-0700 temporary Git revert, push, and create PR |
| `pr review [<number> \| <url> \| <branch>]` | - | Exactly one review action; TTY prompt when omitted | Comment-only is exact; approve/request-changes are the D05 non-atomic comment plus participant update |
| `pr status` | - | Current branch, created-by-viewer, and needs-review groups | Dashboard, build-status, and mergeability REST |
| `pr unlock {<number> \| <url>}` | - | Unlock conversation | N03; not registered because Bitbucket has no conversation-lock concept |
| `pr update-branch [<number> \| <url> \| <branch>]` | - | Merge base into head by default; optional rebase | Temporary/local Git merge or Bitbucket rebase REST |
| `pr view [<number> \| <url> \| <branch>]` | - | Human detail; current-branch inference; optional comments or web | PR, activities, comments, and web link |

### Pull Request Command Availability

| Atomic surface | Contract | Status |
|---|---|---|
| `checkout`, `checks`, `close`, `comment`, `create`, `diff`, `edit`, `list`, `merge`, `reopen`, `revert`, `review`, `status`, `update-branch`, and `view` without a separately blocked flag/value/field | Base command grammar and behavior are implementable | M |
| `pr lock` | Conversation lock is a GitHub-only concept | N03 |
| `pr ready` | Draft/ready state is unavailable in Bitbucket 6.7.2 | N03 |
| `pr unlock` | Conversation unlock is a GitHub-only concept | N03 |

### Pull Request Flags

| Command | Flag | gh contract and Bitbucket mapping | Status |
|---|---|---|---|
| all applicable | `-R, --repo [HOST/]OWNER/REPO` | Explicit repository; PR URL still wins | M |
| checkout | `-b, --branch string` | Local branch name; defaults to head branch | M |
| checkout | `--detach` | Detached checkout | M |
| checkout | `-f, --force` | Reset an existing local branch to latest PR head | M |
| checkout | `--recurse-submodules` | Update all submodules after checkout | M |
| checks | `--fail-fast` | Requires `--watch`; stop on first failure | M |
| checks | `-i, --interval int` | Watch refresh interval; default 10 seconds; requires `--watch` | M |
| checks | `-q, --jq expression` | Common formatter | M |
| checks | `--json fields` | Parser and mapped checks fields; requested fields are classified below | M |
| checks | `--required` | Only individually required checks; 6.7.2 exposes only a required-build count | N03 |
| checks | `-t, --template string` | Common formatter | M |
| checks | `--watch` | Poll until terminal; incompatible with JSON output | M |
| checks | `-w, --web` | Open Bitbucket PR build-status view | M |
| close | `-c, --comment string` | Add comment before decline; if decline fails, retain the successful comment exactly like the baseline | M |
| close | `-d, --delete-branch` | Delete local and writable remote source branch after close | M |
| comment | `-b, --body text` | Comment body | M |
| comment | `-F, --body-file file` | File or `-` stdin | M |
| comment | `--create-if-none` | Valid only with `--edit-last`; create if current user has none | M |
| comment | `--delete-last` | Delete current user's latest comment | M |
| comment | `--edit-last` | Edit current user's latest comment | M |
| comment | `-e, --editor` | Editor input | M |
| comment | `-w, --web` | Open PR comment UI | M |
| comment | `--yes` | Skip `--delete-last` confirmation | M |
| create | `-a, --assignee login` | Bitbucket 6.7.2 PRs have no assignee | N03 |
| create | `-B, --base branch` | Destination branch | M |
| create | `-b, --body string` | PR description | M |
| create | `-F, --body-file file` | File or stdin description | M |
| create | `-d, --draft` | No draft state | N03 |
| create | `--dry-run` | Render resolved creation details; may still push like baseline | M |
| create | `-e, --editor` | First line title, remaining text body | M |
| create | `-f, --fill` | Title/body from commit information | M |
| create | `--fill-first` | First commit title/body | M |
| create | `--fill-verbose` | Commit subjects and bodies | M |
| create | `-H, --head branch` | Source branch; defaults current branch | M |
| create | `-l, --label name` | Bitbucket 6.7.2 has no PR label concept | N03 |
| create | `-m, --milestone name` | No PR milestone concept | N03 |
| create | `--no-maintainer-edit` | No per-PR maintainer-edit permission | N03 |
| create | `-p, --project title` | Bitbucket project is a namespace, not GitHub Projects | N03 |
| create | `--recover string` | Recover local prompt state from a failed run | M |
| create | `-r, --reviewer <user>` | Resolve and add an individual Bitbucket user reviewer | M |
| create | `-r, --reviewer <team-or-copilot>` | Pull request reviewers in 6.7.2 accept user identities, not groups, team slugs, or Copilot | N03 |
| create | `-T, --template file` | Initial body template | M |
| create | `-t, --title string` | PR title | M |
| create | `-w, --web` | Open Bitbucket create-PR UI with resolved refs | M |
| diff | `--color string` | `always\|never\|auto`, default `auto` | M |
| diff | `-e, --exclude patterns` | Repeatable forward-slash glob filtering | M |
| diff | `--name-only` | Changed path list | M |
| diff | `--patch` | Patch endpoint/output | M |
| diff | `-w, --web` | Open Bitbucket diff tab | M |
| edit | `--add-assignee login` | No assignee concept | N03 |
| edit | `--add-label name` | No PR label concept | N03 |
| edit | `--add-project title` | No GitHub Projects concept | N03 |
| edit | `--add-reviewer <user>` | Resolve and add an individual Bitbucket user reviewer | M |
| edit | `--add-reviewer <team-or-copilot>` | Reviewer endpoint accepts individual users only | N03 |
| edit | `-B, --base branch` | Update destination branch | M |
| edit | `-b, --body string` | Update description | M |
| edit | `-F, --body-file file` | Update description from file/stdin | M |
| edit | `-m, --milestone name` | No milestone concept | N03 |
| edit | `--remove-assignee login` | No assignee concept | N03 |
| edit | `--remove-label name` | No PR label concept | N03 |
| edit | `--remove-milestone` | No milestone concept | N03 |
| edit | `--remove-project title` | No GitHub Projects concept | N03 |
| edit | `--remove-reviewer <user>` | Remove an individual Bitbucket user reviewer | M |
| edit | `--remove-reviewer <team-or-copilot>` | Reviewer endpoint accepts individual users only | N03 |
| edit | `-t, --title string` | Update title | M |
| list | `--app string` | No GitHub App author identity | N03 |
| list | `-a, --assignee string` | No assignee concept | N03 |
| list | `-A, --author string` | Author filter, including current user | M |
| list | `-B, --base string` | Destination branch filter | M |
| list | `-d, --draft` | No draft state | N03 |
| list | `-H, --head string` | Source branch filter | M |
| list | `-q, --jq expression` | Common formatter | M |
| list | `--json fields` | Parser and mapped PR fields; requested fields are classified below | M |
| list | `-l, --label strings` | No PR label concept | N03 |
| list | `-L, --limit int` | Default 30; page until satisfied | M |
| list | `-S, --search <mapped-query>` | Text, state, author, review, check, and ref qualifiers that use mapped fields | M |
| list | `-S, --search <query-using-draft>` | Query requires draft state | N03 |
| list | `-S, --search <query-using-assignee>` | Query requires PR assignees | N03 |
| list | `-S, --search <query-using-label>` | Query requires PR labels | N03 |
| list | `-S, --search <query-using-milestone>` | Query requires milestones | N03 |
| list | `-S, --search <query-using-project>` | Query requires GitHub Projects | N03 |
| list | `-S, --search <query-using-app-or-team>` | Query requires GitHub App or team identity | N03 |
| list | `-s, --state string` | Bitbucket-native `OPEN\|DECLINED\|MERGED\|ALL`, case-insensitive; native names remain in output | D08 |
| list | `-t, --template string` | Common formatter | M |
| list | `-w, --web` | Open Bitbucket PR list | M |
| lock | `-r, --reason string` | Entire conversation-lock operation is not registered | N03 |
| merge | `--admin` | No per-merge administrator bypass | N03 |
| merge | `-A, --author-email text` | 6.7.2 merge API has no commit-author parameter | B13 |
| merge | `--auto` | No deferred auto-merge or queue | N03 |
| merge | `-b, --body text` | Official 6.7.2 merge POST exposes no custom commit message body | B13 |
| merge | `-F, --body-file file` | Same custom merge-message blocker | B13 |
| merge | `-d, --delete-branch` | Delete source branch after successful merge | M |
| merge | `--disable-auto` | No auto-merge state | N03 |
| merge | `--match-head-commit SHA` | Compare fetched head SHA before merge | M |
| merge | `-m, --merge=true` when repository default is merge-commit | Read merge settings, verify the requested method equals the configured default, then use merge REST | M |
| merge | `-r, --rebase=true` when repository default is rebase | Read merge settings, verify the requested method equals the configured default, then use merge REST | M |
| merge | `-s, --squash=true` when repository default is squash | Read merge settings, verify the requested method equals the configured default, then use merge REST | M |
| merge | Explicit method different from the repository default | 6.7.2 cannot select a strategy per invocation | B12 |
| merge | No method in non-TTY mode and no merge queue | Exit `1` with `--merge, --rebase, or --squash required when not running interactively`; no mutation | M |
| merge | No method in TTY; selected method equals repository default | Show the baseline method prompt and use merge REST after confirmation | M |
| merge | No method in TTY; selected method differs from repository default | Accept the selection, then fail capability preflight before confirmation or mutation | B12 |
| merge | `-t, --subject text` | No custom merge subject parameter | B13 |
| ready | `--undo` | Entire ready/draft operation is not registered | N03 |
| reopen | `-c, --comment string` | Add comment before reopen; if reopen fails, retain the successful comment exactly like the baseline | M |
| revert | `-b, --body string` | New revert PR body | M |
| revert | `-F, --body-file file` | New revert PR body from file/stdin | M |
| revert | `-d, --draft` | Draft result is unavailable | N03 |
| revert | `-t, --title string` | New revert PR title | M |
| review | `-a, --approve` | Comment if present, then APPROVED participant state; separate operations with compensation | D05 |
| review | `-b, --body string` | Review comment body | M |
| review | `-F, --body-file file` | Review comment from file/stdin | M |
| review | `-c, --comment` | Ordinary review comment, no state change | M |
| review | `-r, --request-changes` | Comment plus NEEDS_WORK participant state with compensation; not an atomic review record | D05 |
| status | `-c, --conflict-status` | Enrich each PR through mergeability REST | M |
| status | `-q, --jq expression` | Common formatter | M |
| status | `--json fields` | Grouped status shape plus individually classified PR fields | M |
| status | `-t, --template string` | Common formatter | M |
| update-branch | `--rebase` | Direct Bitbucket rebase REST; default uses Git merge/push | M |
| view | `-c, --comments` | Include comments | M |
| view | `-q, --jq expression` | Common formatter | M |
| view | `--json fields` | Parser and individually classified PR fields | M |
| view | `-t, --template string` | Common formatter | M |
| view | `-w, --web` | Open Bitbucket PR URL | M |

## Repository Command Inventory

This table is a non-normative summary. N rows remain in the capability index but
are not registered as commands or options.

| Command and usage | Alias | Default and observable behavior | Bitbucket implementation summary |
|---|---|---|---|
| `repo archive [<repository>]` | - | Current repository; confirmation unless `--yes` | N03; no persistent archive lifecycle state |
| `repo autolink <command>` | nested aliases below | Repository selected with `-R` or current context | N03; no autolink resource or concept |
| `repo clone <repository> [<directory>] [-- <gitflags>...]` | - | Command-specific bare/full/URL/`.wiki` behavior; fork adds parent upstream | Clone links, fork origin, and Git |
| `repo create [<name>]` | `new` | No name and no flags: TTY prompts; otherwise exact visibility and dependency rules apply | Repository REST plus Git initialization/push |
| `repo credits [<repository>]` | hidden | Source-hidden baseline command | N01; not copied |
| `repo delete [<repository>]` | - | Current repo allowed; `--yes` ignored without explicit repo | Repository DELETE and confirmation |
| `repo deploy-key <command>` | nested alias below | Current/`-R` repository | Repository access-key REST |
| `repo edit [<repository>]` | - | Current repo; boolean flags accept explicit `=false` | Repository, labels, permissions, default-branch, and PR-settings REST |
| `repo fork [<repository>] [-- <gitflags>...]` | - | Current repo; fork becomes origin and old origin becomes upstream by default | Fork REST plus Git remotes |
| `repo garden [<repository>]` | hidden | Source-hidden baseline command | N01; not copied |
| `repo gitignore <command>` | nested alias below | Versioned template catalog | Bundled baseline catalog |
| `repo license <command>` | nested alias below | Versioned license catalog | Bundled baseline catalog |
| `repo list [<owner>]` | `ls` | Owner defaults authenticated user; limit 30 | Project/personal repository paging and derived filters |
| `repo read-dir [<path>]` | - | Root/default branch by default; exact TTY, TSV, and JSON modes below | Temporary bare fetch plus byte-safe Git tree inspection |
| `repo read-file <path>` | - | Default branch; exact TTY, pipe, JSON, and file-output modes below | Raw REST plus Git metadata |
| `repo rename [<new-name>]` | - | Current repo; prompts for name/confirmation as baseline | Repository PUT; slug follows name |
| `repo set-default [<repository>]` | - | Remote or selector; no argument TTY picker | Local remote marker |
| `repo sync [<destination-repository>]` | - | Destination current; source fork parent; fast-forward by default | Local/temporary Git fetch and push |
| `repo unarchive [<repository>]` | - | Current repository; confirmation unless `--yes` | N03; no persistent archive lifecycle state |
| `repo view [<repository>]` | - | Current repository; metadata plus README | Repository/readme/raw REST |

### Repository Command Availability

| Atomic surface | Contract | Status |
|---|---|---|
| `repo archive` | Persistent repository archive transition has no Bitbucket meaning | N03 |
| `repo autolink create`, `delete`, `list`, and `view` | Autolinks are a GitHub-only repository concept | N03 |
| `repo clone` except the `.wiki` selector value | Clone repository and configure fork upstream | M |
| `repo create` default or interactive path without an explicit feature-enable request | Create the repository successfully; Bitbucket has no issues/wiki to enable | D02 |
| `repo create` with `--disable-issues=true` and/or `--disable-wiki=true`, and no separately blocked value | Explicitly request the provider's already-disabled feature state | M |
| `repo create` with an explicit public flag value requesting issues or wiki enabled | Server 6.7.2 has neither repository feature | B19 |
| Hidden `repo credits` and `repo garden` | Source-hidden GitHub commands | N01 |
| `repo delete`, `repo edit`, `repo fork`, `repo read-dir`, `repo read-file`, `repo rename`, `repo set-default`, `repo sync`, and `repo view` without a separately blocked value/field/mode | Base behavior is implementable | M |
| `repo gitignore list`, `repo gitignore view`, `repo license list`, and `repo license view` | Versioned catalog behavior | M |
| `repo deploy-key add` and `repo deploy-key delete` | Access-key mutations | M |
| Non-empty `repo deploy-key list` default human mode | Render `CREATED AT` as `-`; explicit JSON `createdAt` remains B23 | D04 |
| Empty `repo deploy-key list` in default human mode or JSON requesting only mapped fields | When stdout is a TTY, write `no deploy keys found in DEMO/example-repo` to stderr; non-TTY is silent; both exit `0` | M |
| `repo deploy-key list --json` requesting only mapped fields | Structured list without `createdAt` | M |
| Non-empty `repo list` default human mode | Stable `nameWithOwner` ascending order; render `UPDATED` as `-` | D03 |
| Non-empty `repo list --json` requesting only mapped list fields | Stable `nameWithOwner` ascending order instead of unavailable `PUSHED_AT DESC` | D03 |
| Empty `repo list` in human mode or JSON requesting only mapped fields | Ordering and timestamp cells are unobservable; preserve the baseline empty-result output and exit | M |
| `repo unarchive` | Persistent repository unarchive transition has no Bitbucket meaning | N03 |

### Nested Repository Command Inventory

| Command | Alias | Flags | Mapping summary |
|---|---|---|---|
| `autolink create <keyPrefix> <urlTemplate>` | `new` | `-n, --numeric`; parent `-R` | No autolink resource |
| `autolink delete <id>` | - | `--yes`; parent `-R` | No autolink resource |
| `autolink list` | `ls` | JSON flags, `-w, --web`; parent `-R` | No autolink resource |
| `autolink view <id>` | - | JSON flags; parent `-R` | No autolink resource |
| `deploy-key add <key-file>` | - | `-w, --allow-write`; `-t, --title`; parent `-R` | Access key POST; write permission; title becomes the public-key label/comment |
| `deploy-key delete <key-id>` | - | parent `-R` | Repository access-key DELETE |
| `deploy-key list` | `ls` | JSON flags; parent `-R` | Repository access-key GET |
| `gitignore list` | `ls` | none | Bundled baseline template names |
| `gitignore view <template>` | - | none | Exact bundled template bytes |
| `license list` | `ls` | none | Bundled baseline license catalog |
| `license view {<license-key> \| <spdx-id>}` | - | `-w, --web` | Exact catalog content or choosealicense page |

### Repository Flags

| Command | Flag | gh contract and Bitbucket mapping | Status |
|---|---|---|---|
| archive | `-y, --yes` | Containing command is not registered | N03 |
| archive | `--confirm` (deprecated) | Deprecated flag is not copied | N02 |
| clone | `--no-upstream` | Do not add parent remote for a fork | M |
| clone | `-u, --upstream-remote-name string` | Parent remote name; default `upstream`; sentinel `@owner` uses the parent owner name | M |
| create | `--add-readme` | Commit README to initial branch | M |
| create | `-c, --clone` | Clone new repository | M |
| create | `-d, --description string` | Repository update after creation | M |
| create | `--disable-issues=true` | Bitbucket already has no GitHub repository issue feature; preserve the disabled state as a no-op | M |
| create | `--disable-issues=false` | Retains the baseline enabled-issues default, which 6.7.2 cannot represent | B19 |
| create | `--disable-wiki=true` | Bitbucket already has no GitHub-style repository wiki; preserve the disabled state as a no-op | M |
| create | `--disable-wiki=false` | Retains the baseline enabled-wiki default, which 6.7.2 cannot represent | B19 |
| create | `--enable-issues[=value]` (deprecated) | Deprecated GitHub inverse flag is not copied | N02 |
| create | `--enable-wiki[=value]` (deprecated) | Deprecated GitHub inverse flag is not copied | N02 |
| create | `-y, --confirm` (deprecated) | Deprecated GitHub flag is not copied | N02 |
| create | `-g, --gitignore string` | Commit selected baseline template | M |
| create | `-h, --homepage <nonempty-URL>` | Repository model has no homepage field | B16 |
| create | `-h, --homepage ""` | Preserve the baseline empty homepage as a no-op | M |
| create | `--include-all-branches` | With template, fetch and push all branches | M |
| create | `--internal=true` | No internal visibility tier | B17 |
| create | `-l, --license string` | Commit selected baseline license | M |
| create | `--private=true` | Set repository public false | M |
| create | `--public=true` | Set repository public true | M |
| create | `--public=false`, `--private=false`, or `--internal=false` | Parse as false and do not satisfy the required visibility choice; another true visibility value may still satisfy it | M |
| create | `--push` | Push source repository refs | M |
| create | `-r, --remote string` | Add local Git remote | M |
| create | `-s, --source string` | Use local repository as source | M |
| create | `-t, --team name` | Resolve an exact Bitbucket group and grant `REPO_WRITE` through repository group permissions after creation; roll back the repository if the grant fails | M |
| create | `-p, --template repository` | Clone template content into an independent new repository | M |
| delete | `--yes` | Skip confirmation only with explicit repository | M |
| delete | `--confirm` (deprecated) | Deprecated GitHub spelling is not copied | N02 |
| edit | `--accept-visibility-change-consequences` | Required for visibility change | M |
| edit | `--add-topic <valid-label>` | Add a lowercase 3-50 character repository label | M |
| edit | `--add-topic <one-or-two-character-topic>` | Bitbucket repository labels have a three-character minimum | B29 |
| edit | `--allow-forking=true\|false` | Repository `forkable` | M |
| edit | `--allow-update-branch[=value]` | GitHub-only repository policy is not registered | N03 |
| edit | `--default-branch name` | Default-branch PUT | M |
| edit | `--delete-branch-on-merge[=value]` | GitHub-only repository policy is not registered | N03 |
| edit | `-d, --description string` | Repository PUT | M |
| edit | `--enable-advanced-security[=value]` | GitHub Advanced Security is not a Bitbucket 6.7.2 concept | N03 |
| edit | `--enable-auto-merge[=value]` | GitHub auto-merge is not a Bitbucket 6.7.2 concept | N03 |
| edit | `--enable-discussions[=value]` | GitHub discussions are not a Bitbucket 6.7.2 concept | N03 |
| edit | `--enable-issues[=value]` | GitHub issues are not a Bitbucket 6.7.2 concept | N03 |
| edit | `--enable-merge-commit=true\|false` | Update enabled merge strategies in PR settings | M |
| edit | `--enable-projects[=value]` | Bitbucket project is a namespace, not GitHub Projects | N03 |
| edit | `--enable-rebase-merge=true\|false` | Update enabled merge strategies in PR settings | M |
| edit | `--enable-secret-scanning[=value]` | GitHub secret scanning is not a Bitbucket 6.7.2 concept | N03 |
| edit | `--enable-secret-scanning-push-protection[=value]` | GitHub push protection is not a Bitbucket 6.7.2 concept | N03 |
| edit | `--enable-squash-merge=true\|false` | Update enabled merge strategies in PR settings | M |
| edit | `--enable-wiki[=value]` | GitHub wiki toggle is not a Bitbucket 6.7.2 concept | N03 |
| edit | `-h, --homepage <nonempty-URL>` | No homepage field | B16 |
| edit | `-h, --homepage ""` | Succeed as an idempotent clear because Bitbucket has no homepage value | M |
| edit | `--remove-topic <valid-label>` | Remove repository labels | M |
| edit | `--remove-topic <one-or-two-character-topic>` | Return success without mutation because Bitbucket cannot contain a corresponding short label | M |
| edit | `--squash-merge-commit-message string` | GitHub-specific message policy is not registered | N03 |
| edit | `--template[=value]` | Persistent GitHub template-repository property is not registered | N03 |
| edit | `--visibility public\|private` | Map to the repository public boolean | M |
| edit | `--visibility internal` | No internal visibility tier | B17 |
| fork | `--clone` | Clone created fork | M |
| fork | `--default-branch-only` | Fork API has no atomic parameter; post-fork ref deletion is not equivalent and may leave residue | B33 |
| fork | `--fork-name string` | Fork POST name | M |
| fork | `--org string` | Target project key | M |
| fork | `--remote` | Add fork remote | M |
| fork | `--remote-name string` | Fork remote name; default `origin` | M |
| list | `--archived` | Archive-state filtering is not registered | N03 |
| list | `--fork` | Filter repositories with origin | M |
| list | `-q, --jq expression` | Common formatter | M |
| list | `--json fields` | Parser and individually classified repository fields | M |
| list | `-l, --language string` | Would require unbounded multi-repository content fetch/clone fan-out | N04 |
| list | `-L, --limit int` | Default 30; page until satisfied | M |
| list | `--no-archived` | Archive-state filtering is not registered | N03 |
| list | `--private` (deprecated) | Deprecated GitHub flag is not copied; use `--visibility private` | N02 |
| list | `--public` (deprecated) | Deprecated GitHub flag is not copied; use `--visibility public` | N02 |
| list | `--source` | Filter repositories without origin | M |
| list | `-t, --template string` | Common formatter | M |
| list | `--topic <valid-label>` | Filter repository labels | M |
| list | `--topic <one-or-two-character-topic>` | Return the mapped empty result because Bitbucket cannot contain a corresponding short label | M |
| list | `--visibility public\|private` | Filter the repository public boolean | M |
| list | `--visibility internal` | No internal visibility tier | B17 |
| read-dir | `-q, --jq expression` | Common formatter | M |
| read-dir | `--json fields` | Read-directory field set below | M |
| read-dir | `--ref string` | Branch, tag, or commit; default repository branch | M |
| read-dir | `-R, --repo ...` | Common selector | M |
| read-dir | `-t, --template string` | Common formatter | M |
| read-file | `--allow-escape-sequences` | Permit unsafe terminal bytes | M |
| read-file | `--clobber` | Permit replacing output file | M |
| read-file | `-q, --jq expression` | Common formatter | M |
| read-file | `--json fields` | Parser and individually classified read-file fields | M |
| read-file | `-o, --output path` | Destination path, never an output format | M |
| read-file | `--ref string` | Branch, tag, or commit; default repository branch | M |
| read-file | `-R, --repo ...` | Common selector | M |
| read-file | `-t, --template string` | Common formatter | M |
| rename | `-R, --repo ...` | Select another repository | M |
| rename | `-y, --yes` | Skip confirmation | M |
| rename | `--confirm` (deprecated) | Deprecated GitHub spelling is not copied | N02 |
| credits | `-s, --static` | Source-hidden containing command is not copied | N01 |
| set-default | `-u, --unset` | Idempotently clear local default | M |
| set-default | `-v, --view` | Print canonical current default | M |
| sync | `-b, --branch string` | Default source default branch | M |
| sync | `--force` | Hard-reset/force destination to source | M |
| sync | `-s, --source string` | Explicit source; default fork parent | M |
| unarchive | `-y, --yes` | Containing command is not registered | N03 |
| unarchive | `--confirm` (deprecated) | Deprecated flag is not copied | N02 |
| view | `-b, --branch string` | Read README at branch | M |
| view | `-q, --jq expression` | Common formatter | M |
| view | `--json fields` | Parser and individually classified repository fields | M |
| view | `-t, --template string` | Common formatter | M |
| view | `-w, --web` | Open repository web page | M |

## Parser, Precedence, and Prompt Contract

Rows in this section classify parser and interaction behavior directly. A later
capability failure does not bypass mapped syntax checks. Unless a row says
otherwise, validation completes before network or filesystem mutation.

### Common Rules

| Atomic surface | Exact rule | Status |
|---|---|---|
| Prompt eligibility and TTY override | Match the baseline TTY rules through `ATLASSIAN_PROMPT_DISABLED`, product config, and optional `ATLASSIAN_FORCE_TTY`; do not read `GH_PROMPT_DISABLED` or `GH_FORCE_TTY` | D01 |
| `--json` plus `--jq` or `--template` | `--jq` and `--template` each require `--json` | M |
| `--jq` plus `--template` | Both are accepted; jq takes precedence and template is ignored | M |
| `--web` plus `--json` on `pr checks`, `pr list`, `pr view`, or `repo view` | Exit `1` with `cannot use \`--web\` with \`--json\`` before repository resolution, browser launch, or network I/O | M |
| Explicit PR URL plus `-R`/`ATLASSIAN_BITBUCKET_REPO`/remotes | The URL repository and PR ID are authoritative | M |
| Omitted optional PR selector plus `-R` | Registered `checks`, `comment`, `diff`, `merge`, `review`, `update-branch`, and `view` exit `1` with the baseline argument-required error; `ready` is N03 | M |
| Omitted PR selector on `edit -R` | Infer the current branch instead of applying the argument-required guard | M |
| Omitted PR selector on `checkout -R` | Use the selected repository for the 10-item TTY picker; non-TTY exits `1` | M |
| `status -R` | Do not parse the current branch; omit the current-branch group and render the created-by-viewer and needs-review groups for the selected repository | M |
| N options, including `--required`, draft/assignee/label/project flags, and auto/admin flags | Reject as unknown options because they are not registered | N03 |
| Blocked flag/value mixed with another invalid parser combination | Report the baseline parser error first; capability preflight runs only after argv is syntactically valid | M |

### Pull Request Rules

| Command | Atomic rule | Status |
|---|---|---|
| `checkout` | Omitted selector opens the 10-item TTY picker; non-TTY exits `1` | M |
| `checks` | `--watch` and `--json` are mutually exclusive; `--fail-fast` and an explicitly supplied `--interval` each require `--watch`; interval is parsed as signed integer seconds, and non-positive durations return immediately between polls | M |
| `comment` | Exactly one of `--body`, `--body-file`, `--editor`, or `--web`; `--create-if-none` requires `--edit-last`; `--yes` requires `--delete-last`; delete forbids a body; a non-TTY delete requires `--yes`; no mode/body in non-TTY exits `1` | M |
| `create` body sources | `--body` and `--body-file` may be combined; file content wins regardless of argv order. `--template` cannot accompany either, and `--body-file -` consumes stdin once | M |
| `create` fill sources | At most one of `--fill`, `--fill-first`, and `--fill-verbose` | M |
| `create --web` | For registered options, mutually exclusive with `--editor`, any reviewer, and `--dry-run`; N03 options never enter relation validation | M |
| `create --recover` | TTY-only | M |
| `create` non-TTY | Unless `--web` or a fill mode is used, require both explicit `--title` and explicit body input | M |
| `edit` | `--body` and `--body-file` are mutually exclusive; no registered edit flags opens a TTY editor and exits `1` in non-TTY mode. Milestone options are N03 | M |
| `list` repository | Accept either paired `PROJECT_KEY REPO_SLUG`, `-R PROJECT_KEY/REPO_SLUG`, or repository inference; reject a partial pair and paired positionals combined with `-R` | D07 |
| `list` | Limit must be greater than zero; `--author` is accepted and N03 `--app` is not registered | M |
| `merge` method | At most one of `--merge`, `--rebase`, and `--squash`; conditional capability rows above apply only after this validation | M |
| `merge --body` and `--body-file` | Mutually exclusive before B13 capability preflight | M |
| `merge --auto`, `--disable-auto`, and `--admin` relations | The GitHub-only options are not registered, so their mutual-exclusion group is not copied | N03 |
| `merge` prompt | With no method in TTY, prompt only with methods enabled by repository settings, then confirmation and optional branch deletion; in non-TTY use the exact method-required error described above | M |
| `revert` | `--body` and `--body-file` are mutually exclusive | M |
| `review` body | `--body` and `--body-file` are mutually exclusive | M |
| `review` action | Exactly one of `--approve`, `--request-changes`, or `--comment`; no action opens a TTY prompt, while non-TTY exits `1`; body without an action is invalid; request-changes and comment require a nonblank body | M |
| `close --comment` and `reopen --comment` failure order | Create the comment first; if the state transition fails, return the transition error and retain the successful comment without compensation | M |

### Repository Rules

| Command | Atomic rule | Status |
|---|---|---|
| `clone` | `--no-upstream` and `--upstream-remote-name` are mutually exclusive; Git flags must follow `--`; explicit URL protocol and `.wiki` value handling follow the selector rows above | M |
| `create` interactive entry | No name and no registered flags requires a TTY and starts the baseline three-way prompt; any argument or registered flag selects non-interactive validation | M |
| `create` visibility | Non-interactive mode requires exactly one of `--public`, `--private`, or `--internal` to be true; an explicit false value does not count. Capability classification happens after exclusivity validation | M |
| `create --source` dependencies | `--remote` and `--push` require `--source`; `--source` is incompatible with `--clone`, `--template`, `--license`, and `--gitignore` | M |
| `create --template` dependencies | Template is incompatible with `--gitignore`, `--license`, `--add-readme`, and `--team`; `--include-all-branches` requires template | M |
| `edit` interactive entry | No property flags opens the TTY editor; non-TTY exits `1` | M |
| `edit --visibility` | Requires `--accept-visibility-change-consequences` even before value capability validation | M |
| `edit --squash-merge-commit-message` | GitHub-specific message policy option is not registered | N03 |
| `fork` Git flags | Git flags after `--` require an explicit repository argument | M |
| `fork --remote` | Invalid with an explicit repository argument; blank `--org` and blank `--remote-name` are invalid | M |
| `list` | Limit must be greater than zero; `--source` and `--fork` are mutually exclusive; `--visibility` accepts one value. N02/N03/N04 options are rejected before relation validation | M |
| `read-file` | `--json` and `--output` are mutually exclusive; `--clobber` without `--output` is accepted and has no effect; disk output bypasses binary/escape rejection | M |
| `archive`, `unarchive`, and `autolink` parser rules | Containing commands are not registered | N03 |
| `delete` | With no repository, `--yes` is ignored; non-TTY then errors. An explicit repository plus `--yes` skips confirmation | M |
| `rename` | Omitted new name requires TTY; one positional name without `-R` requires confirmation or `--yes`; `-R` plus a name does not prompt | M |
| `set-default` argument and modes | Argument, `--view`, and `--unset` may be combined. Parse and validate an argument first, then apply `--view` > `--unset` > set/pick precedence | M |
| `set-default` non-TTY guard | With no argument, only `--view` bypasses the repository-required guard; bare `--unset` still exits `1`. With no mode or argument, TTY opens the remote picker and non-TTY exits `1` | M |
| Hidden `garden` | Source-hidden command is not copied | N01 |
| Existing per-command legacy `--output` | Hidden and deprecated compatibility input on commands that already expose it; selects the v0.1.19 renderer. New commands do not gain it | D06 |
| `repo read-file -o, --output` | Command-local destination path, never a structured format | M |

## JSON Field Contract

### Pull Request Resource Fields

Used by `pr list`, `pr status`, and `pr view`.

| Status | Fields | Source or blocker |
|---|---|---|
| M | `author`, `baseRefName`, `baseRefOid`, `body`, `closed`, `closedAt`, `commits`, `createdAt`, `fullDatabaseId`, `headRefName`, `headRefOid`, `headRepository`, `headRepositoryOwner`, `id`, `isCrossRepository`, `number`, `state`, `title`, `updatedAt`, `url` | Direct PR, ref, commit, and link REST projection; dates normalize to RFC3339 |
| M | `additions`, `changedFiles`, `comments`, `deletions`, `files`, `mergeStateStatus`, `mergeable`, `mergedAt`, `mergedBy`, `reviewDecision`, `reviewRequests` | Derived from diffs, activities, participants, and mergeability |
| M | `statusCheckRollup` | Project each build as `{"__typename":"StatusContext","context":key,"state":normalized-state,"targetUrl":url,"startedAt":RFC3339(dateAdded)}`; use `[]` for a resolved head with no builds |
| N03 | `assignees`, `autoMergeRequest`, `closingIssuesReferences`, `isDraft`, `labels`, `maintainerCanModify`, `milestone`, `projectCards`, `projectItems`, `reactionGroups` | GitHub-only fields are not in the accepted field list |
| B30 | `latestReviews`, `reviews` | Participant state and comments do not provide immutable, atomic review records |
| B31 | `mergeCommit` | A merged PR has no stable merge-commit identity in the 6.7.2 PR representation or activity contract |
| B25 | `potentialMergeCommit` | No documented potential merge object or stable ref |

`pr status --json` returns an object with `currentBranch`, `createdBy`, and
`needsReview`; requested PR fields are projected inside those entries.

### Checks Fields

| Field | Mapping | Status |
|---|---|---|
| `bucket` | Derive `pass`, `fail`, or `pending` from build state | M |
| `description` | Build description | M |
| `link` | Build URL | M |
| `name` | Build name, then key | M |
| `state` | Normalize SUCCESSFUL/FAILED/INPROGRESS to SUCCESS/FAILURE/PENDING | M |
| `workflow` | Empty string, matching the baseline aggregate for a `StatusContext` | M |
| `completedAt` | `0001-01-01T00:00:00Z`, the baseline zero `time.Time` for a `StatusContext` | M |
| `event` | Empty string, matching the baseline aggregate for a `StatusContext` | M |
| `startedAt` | `0001-01-01T00:00:00Z`, the baseline zero `time.Time` for a `StatusContext` | M |

### Repo List Fields

The accepted list field set is intentionally narrower than `repo view`. A field
that requires cloning, browsing files, or a per-repository auxiliary REST call is
N04 for list even when one bounded `repo view` can provide it.

| Status | Fields | Source or blocker |
|---|---|---|
| M | `defaultBranchRef`, `description`, `forkCount`, `id`, `isEmpty`, `isFork`, `isInOrganization`, `isPrivate`, `name`, `nameWithOwner`, `owner`, `parent`, `sshUrl`, `url`, `visibility` | Direct repository-list projection |
| M | `archivedAt=null`, `latestRelease=null`, `templateRepository=null`, `homepageUrl=""`, `mirrorUrl=""`, `openGraphImageUrl=""`, `stargazerCount=0` | Provider-accurate constants with the baseline exported types |
| M | `isArchived=false`, `isBlankIssuesEnabled=false`, `hasDiscussionsEnabled=false`, `hasIssuesEnabled=false`, `hasProjectsEnabled=false`, `hasWikiEnabled=false`, `isMirror=false`, `isTemplate=false`, `isUserConfigurationRepository=false`, `usesCustomOpenGraphImage=false`, `viewerHasStarred=false`, `deleteBranchOnMerge=false` | False constants for absent provider states and features |
| N04 | `codeOfConduct`, `fundingLinks`, `issueTemplates`, `isSecurityPolicyEnabled`, `languages`, `licenseInfo`, `mentionableUsers`, `mergeCommitAllowed`, `primaryLanguage`, `pullRequestTemplates`, `pullRequests`, `rebaseMergeAllowed`, `repositoryTopics`, `securityPolicyUrl`, `squashMergeAllowed`, `viewerCanAdminister`, `viewerDefaultMergeMethod`, `viewerPermission` | Requires per-repository content or auxiliary requests and is not accepted by list |
| B32 | `assignableUsers` | No permission-complete assignable-user directory |
| B23 | `createdAt`, `diskUsage`, `pushedAt`, `updatedAt`, `watchers`, `viewerDefaultCommitEmail`, `viewerPossibleCommitEmails`, `viewerSubscription` | Repository/list APIs do not expose equivalent lifecycle or viewer metadata |
| N03 | `contactLinks`, `issues`, `labels`, `milestones`, `projects`, `projectsV2` | GitHub-only fields are not in the accepted list field set |

### Repo View Fields

| Status | Fields | Source or blocker |
|---|---|---|
| M | `defaultBranchRef`, `description`, `forkCount`, `id`, `isEmpty`, `isFork`, `isInOrganization`, `isPrivate`, `licenseInfo`, `name`, `nameWithOwner`, `owner`, `parent`, `sshUrl`, `url`, `viewerCanAdminister`, `viewerPermission`, `visibility` | Direct repository, fork, branch, license, permission, and link projection |
| M | `codeOfConduct`, `fundingLinks`, `issueTemplates`, `languages`, `mentionableUsers`, `primaryLanguage`, `pullRequestTemplates`, `pullRequests`, `repositoryTopics`, `securityPolicyUrl`, `isSecurityPolicyEnabled` | Bounded single-repository derivation from user APIs, repository files, Git content, PR REST, and repository labels |
| M | `mergeCommitAllowed`, `rebaseMergeAllowed`, `squashMergeAllowed`, `viewerDefaultMergeMethod` | Pull-request merge settings |
| M | `archivedAt=null`, `latestRelease=null`, `templateRepository=null`, `homepageUrl=""`, `mirrorUrl=""`, `openGraphImageUrl=""`, `stargazerCount=0` | Provider-accurate constants with the baseline exported types |
| M | `isArchived=false`, `isBlankIssuesEnabled=false`, `hasDiscussionsEnabled=false`, `hasIssuesEnabled=false`, `hasProjectsEnabled=false`, `hasWikiEnabled=false`, `isMirror=false`, `isTemplate=false`, `isUserConfigurationRepository=false`, `usesCustomOpenGraphImage=false`, `viewerHasStarred=false`, `deleteBranchOnMerge=false` | False constants for absent provider states and features |
| B32 | `assignableUsers` | No permission-complete assignable-user directory |
| B23 | `createdAt`, `diskUsage`, `pushedAt`, `updatedAt`, `watchers`, `viewerDefaultCommitEmail`, `viewerPossibleCommitEmails`, `viewerSubscription` | Repository API exposes no equivalent lifecycle or viewer metadata |
| N03 | `contactLinks`, `issues`, `labels`, `milestones`, `projects`, `projectsV2` | GitHub-only fields are not in the accepted view field set |

### Deploy Key Fields

| Field | Mapping | Status |
|---|---|---|
| `id` | Access key ID | M |
| `key` | Public key text | M |
| `readOnly` | Permission is REPO_READ | M |
| `title` | Access key label/public-key comment | M |
| `createdAt` | Access-key payload has no timestamp | B23 |

### Read Directory Fields

| Atomic surface | Exact mapping | Status |
|---|---|---|
| JSON envelope | Always emit `{"id":...,"gitSHA":...,"entries":[...]}`; requested fields select properties inside each entry only | M |
| `id` and envelope `gitSHA` | Use the resolved tree SHA as the provider tree identity and Git SHA | M |
| Entry fields | Map `gitSHA`, `gitType`, `mode`, `modeOctal`, `name`, `nameRaw`, `path`, `pathRaw`, `size`, `submodule`, and `type` through byte-safe Git tree/object inspection | M |
| `type` and `gitType` | Map modes to `dir`, `file`, `symlink`, `submodule`, or `unknown`; corresponding known Git object types are `tree`, `blob`, `blob`, and `commit` | M |
| `modeOctal` | Six lowercase octal digits such as `100644`, `040000`, `120000`, or `160000` | M |
| `submodule` | `null` for non-gitlinks and for gitlinks whose `.gitmodules` metadata cannot be resolved; otherwise `{gitUrl,branch,subprojectCommitOid}` with nullable `branch` | M |
| Non-TTY human output | No header; one `type<TAB>name<TAB>modeOctal<TAB>size` line per entry | M |
| TTY human output | Pager-backed `Showing N entry in ...` or `Showing N entries in ...`, blank line, then `TYPE NAME SIZE`; executable files render as `file*`, files/symlinks use human-readable size, and directories/submodules use `-`. Pager-start failure warns on stderr and still renders | M |
| Empty directory | JSON emits the structural envelope with `entries:[]`; human mode writes `No entries found in DEMO/example-repo[/path]` to stderr, writes no stdout, and exits `0` | M |
| Missing path/ref or non-directory | Preserve the baseline path-only, path-plus-ref, file-not-directory, and generic non-directory errors and exit `1` | M |

### Read File Fields

| Status | Fields | Source or blocker |
|---|---|---|
| M | `content`, `downloadUrl`, `encoding`, `gitSHA`, `htmlUrl`, `name`, `path`, `size`, `type`, `url` | Raw/browse REST plus Git object metadata |
| B26 | `gitUrl` | No GitHub Git Blob API equivalent URL |

| Atomic surface | Exact mapping | Status |
|---|---|---|
| JSON content | Export `content` as standard padded base64 and `encoding` as the fixed string `base64`; fetch raw bytes only when selected content was not returned inline. An empty file exports `content:""` without a warning | M |
| JSON/output conflict | `--json` and `--output` are mutually exclusive; `--clobber` without `--output` is accepted and has no effect | M |
| Accepted object type | Require a regular file; preserve distinct directory, symlink, submodule, and unknown-type errors and exit `1` | M |
| Empty file in stdout human mode | Write the baseline warning icon plus `file is empty` to stderr, no content to stdout, and exit `0`; JSON and disk-output modes follow their own rows | M |
| TTY content | Start the pager and write bytes without adding a newline; pager-start failure is warned on stderr and content still renders | M |
| Non-TTY content | Write raw bytes without transformation or an added newline | M |
| Binary detection | Apply Go `net/http.DetectContentType` semantics to the leading bytes, strip any `;` parameter, and treat only `text/*` as text; handle empty content before detection | M |
| Binary content | TTY returns the baseline MIME/size error; non-TTY writes raw bytes and exits according to the write result | M |
| Escape sequences | After binary classification, reject non-binary terminal and piped content containing byte `0x1B` unless `--allow-escape-sequences` is set | M |
| Disk output | Bypass empty, binary, and escape checks; when stdout is a TTY, report the written remote path and destination on stderr | M |
| Output path resolution | Refuse symlinks at either resolved destination; an existing directory or trailing separator receives the remote basename | M |
| Output creation | Create missing parents with mode `0755`, write directly with mode `0644`, and do not use a temporary-file rename | M |
| Existing output | Without `--clobber`, return the baseline already-exists error; with it, overwrite the regular destination directly | M |

### Autolink Fields

`id`, `isAlphanumeric`, `keyPrefix`, and `urlTemplate` are all N03 with the
non-applicable autolink command group and are not accepted fields.

## Blocker Evidence

| Code | Missing capability | Bitbucket 6.7.2 evidence and why Git cannot replace it |
|---|---|---|
| B12 | Per-invocation merge strategy | Merge POST accepts the optimistic PR `version` but no strategy selector; repository settings choose a shared default. Temporarily mutating them requires excess permission, races with other users, affects unrelated merges, and cannot guarantee rollback without residue. Local Git cannot preserve Bitbucket merge checks, hooks, actor, audit/activity, optimistic version, server `MERGED` transition, or one atomic server transaction |
| B13 | Merge author/message controls | Merge POST exposes no author email, subject, or body. A locally authored merge would bypass Bitbucket merge checks, hooks, actor identity, audit/activity, optimistic PR version, server `MERGED` transition, and the atomic server transaction |
| B16 | Non-empty repository homepage | Repository create/update representation has no homepage property; an empty value is independently mapped as the already-absent state |
| B17 | Internal visibility | Repository visibility is public boolean or permissioned private; no internal tier |
| B19 | Explicit issues/wiki enable request | Public `repo create --disable-issues=false` or `--disable-wiki=false` requests a feature state absent from the 6.7.2 repository contract |
| B23 | Repository/access-key lifecycle and viewer metadata | REST does not expose repository push/create/update times, disk usage, access-key creation time, watcher membership, or the listed viewer email/subscription values; local Git cannot reconstruct server metadata |
| B25 | Potential merge commit | Mergeability API returns status but no stable potential-merge object or documented fetch ref |
| B26 | GitHub Git Blob URL | Raw/browse content exists, but no Git Blob API resource URL |
| B29 | One- or two-character repository topic | Bitbucket repository-label validation requires at least three characters, so the server cannot persist the baseline topic value |
| B30 | Atomic pull-request review records | Reviewers expose current status and `lastReviewedCommit`; activities expose user, action, and time; comments are separate. 6.7.2 cannot bind optional body, state, author association, reviewed commit, reactions, stable review ID, and URL into one immutable review object, and correlating independent records is ambiguous |
| B31 | Pull-request merge-commit identity | The 6.7.2 PR representation, merge response, and activities do not expose a stable merge commit object/ref; guessing from destination history is ambiguous and race-prone |
| B32 | Assignable-user directory | PR participants are not an assignable set, while direct permission endpoints require elevated access and omit inherited/global membership needed for a complete result |
| B33 | Atomic default-branch-only fork | Fork POST has no ref-selection parameter. A full fork followed by ref deletion exposes extra refs, can race with readers, and can leave a partially reduced fork |

## Deviation Evidence

| Code | Deviation | Required behavior |
|---|---|---|
| D01 | Product environment namespace | Use `ATLASSIAN_BITBUCKET_REPO`, `ATLASSIAN_EDITOR`, `ATLASSIAN_BROWSER`, `ATLASSIAN_PAGER`, `ATLASSIAN_PROMPT_DISABLED`, and optional `ATLASSIAN_FORCE_TTY`; retain standard `GIT_EDITOR`, `VISUAL`, `EDITOR`, `BROWSER`, and `PAGER` fallbacks; ignore `GH_*` counterparts |
| D02 | Repository creation without GitHub issues/wiki | Default and interactive `repo create` succeed and create the repository; documentation states that Bitbucket Server 6.7.2 has no corresponding issues/wiki features; explicit public enable values remain B19 |
| D03 | Repository list order and updated time | Sort by `nameWithOwner` ascending, render human `UPDATED` as `-`, and never substitute commit time for server push time |
| D04 | Deploy-key creation time | Non-empty human list renders `CREATED AT` as `-`; explicit JSON `createdAt` remains B23 |
| D05 | Pull-request review atomicity | Comment and participant-state update are separate; attempt documented compensation on second-step failure and report any residue; do not claim an atomic review record |
| D06 | Existing output compatibility | Existing per-command `--output` options stay hidden/deprecated and select the v0.1.19 renderer; new parity commands do not gain the option |
| D07 | Pull-request list repository compatibility | Preserve paired `PROJECT_KEY REPO_SLUG` positionals alongside `-R PROJECT_KEY/REPO_SLUG` and repository inference; reject partial or mixed explicit forms before I/O |
| D08 | Bitbucket-native pull-request states | Default to `OPEN`; accept only `OPEN`, `DECLINED`, `MERGED`, and `ALL` case-insensitively in list and search inputs; retain native state names in human and JSON output |

## Not-Applicable Evidence

| Code | Excluded surface | Reason and parser policy |
|---|---|---|
| N01 | Source-hidden `repo credits` and `repo garden` | They are implementation history, not useful public parity requirements; do not register them or `credits --static` |
| N02 | Deprecated GitHub flags | Do not copy deprecated `--confirm`, create `--confirm`/inverse feature flags, or list `--public`/`--private`; existing local compatibility inputs take priority |
| N03 | GitHub-only commands, flags, fields, and values | Bitbucket 6.7.2 has no corresponding product concept. Keep the evidence rows for scope accounting, but omit them from primary help, parser options, enum values, and allowed JSON field lists |
| N04 | Multi-repository content and auxiliary fan-out | `repo list --language` and list fields requiring clone/browse or per-repository auxiliary requests are omitted. Bounded single-repository `repo view` derivation remains allowed |

## Compatibility and Migration Matrix

| v0.1.19 surface | Decision |
|---|---|
| `pr get PROJECT REPO ID` | Hidden compatibility command; old output and exits retained |
| `pr build-status PROJECT REPO ID` | Hidden compatibility command; all-commit default retained |
| `pr approve PROJECT REPO ID` | Hidden compatibility command |
| `pr unapprove PROJECT REPO ID` | Hidden compatibility command |
| `repo get PROJECT REPO` | Hidden compatibility command |
| Old `pr comment` nested CRUD subcommands | Move `list`, `get`, `add`, `reply`, `edit`, and `delete` to documented Bitbucket extension `pr comments ...` |
| `pr list PROJECT REPO` | Retain on the primary command alongside `pr list -R PROJECT/REPO`; both forms use the same filtering, pagination, output, and exit policy |
| Old positionals on same-name `pr diff`, `create`, and `merge` | Breaking migration to gh grammar; no double parser |
| Old full-screen `pr list` browser | Move to `pr browse PROJECT REPO` with the old `--state`, `--start`, and `--limit`; keep interactive browsing plus static Markdown fallback. Primary `pr list` uses baseline line-oriented output and `--web` opens Bitbucket in a web browser |
| Old `repo list --project` and `repo create --project/--name` | Breaking migration to gh grammar |
| Existing per-command legacy `--output` | Retain as a hidden, deprecated compatibility input selecting the v0.1.19 renderer; do not add it to new commands |
| Existing detailed exit codes | Retained by compatibility/non-parity commands; primary parity commands use gh exits |
