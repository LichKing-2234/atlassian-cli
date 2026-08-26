# atlassian-cli

CLI for Atlassian Server and Data Center products.

## Install

`python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`

## Binary Install From GitHub Release

Tagged releases publish PyOxidizer-based standalone bundles for `linux/amd64`, `darwin/arm64`, `darwin/amd64`, and `windows/amd64`, plus `checksums.txt`.

Install the latest Linux or macOS binary release:

```bash
curl -fsSL https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/main/install.sh | sh
```

Install a specific Linux or macOS release:

```bash
curl -fsSL https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/main/install.sh | env INSTALL_VERSION=v0.1.0 sh
```

Install the latest Windows amd64 release from PowerShell:

```powershell
irm https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/main/install.ps1 | iex
```

Install a specific Windows release:

```powershell
$env:INSTALL_VERSION = "v0.1.0"; irm https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/main/install.ps1 | iex
```

By default the Unix shell installer writes an `atlassian` launcher to `~/.local/bin` and installs the runtime bundle under `~/.local/bin/.atlassian-cli`. It supports Linux amd64 and macOS arm64/amd64. The PowerShell installer writes `atlassian.cmd` to the same default install directory on Windows and installs the runtime bundle under `~/.local/bin/.atlassian-cli`.

You can also download a tarball or Windows zip from the GitHub Release page. Unix bundles run `atlassian/atlassian` from the extracted bundle; Windows bundles run `atlassian/atlassian.exe`. If you do not use a Unix-like shell on Windows, download `atlassian-cli_<version>_windows_amd64.zip`, extract it, and run `atlassian/atlassian.exe`.

macOS binaries are unsigned in the first release version, so macOS may require a manual Gatekeeper allow step on first run.

Verify the installed version:

```bash
atlassian --version
```

## Python Package Install From GitHub Release

GitHub Release assets also include a wheel and sdist for Python-managed installs.

Install from a downloaded wheel:

```bash
uv tool install ./atlassian_cli-0.1.12-py3-none-any.whl
```

Install directly from a versioned GitHub Release wheel URL:

```bash
uv tool install \
  https://github.com/LichKing-2234/atlassian-cli/releases/download/v0.1.12/atlassian_cli-0.1.12-py3-none-any.whl
```

This package-managed path is separate from the standalone PyOxidizer binary install path above.

## Update

On interactive commands, the CLI checks for a newer GitHub Release at most once every 24 hours and prints an update notice to stderr when a newer release exists. It never installs updates automatically, and JSON/YAML command output is not modified.

Set `ATLASSIAN_DISABLE_UPDATE_CHECK=1` to disable the automatic check.

Check for a newer GitHub Release:

```bash
atlassian update check
```

For binary installs, install the latest release:

```bash
atlassian update install
```

For binary installs, install a specific release, or choose a non-default install directory:

```bash
atlassian update install --version v0.1.0
atlassian update install --install-dir ~/.local/bin
```

`atlassian update install` uses the same installer and checksum verification as the binary install command. In an interactive terminal it shows the installer's live download progress; in non-interactive output it still suppresses replayed progress noise and keeps the final status plus any actionable PATH reminder. Package-managed installs such as `uv tool install` should be upgraded through the package manager instead of `atlassian update install`, for example:

```bash
uv tool upgrade atlassian-cli
```

## Configure

Run the setup wizard:

```bash
atlassian init
```

Inspect every supported argument:

```bash
atlassian init --help
```

Configure one product:

```bash
atlassian init jira
```

Use flags for non-interactive setup:

```bash
atlassian init bitbucket --deployment dc --url https://bitbucket.example.com --auth pat --token secret
```

For automated Jira and Confluence setup, provide the product credentials as
literal values through the parameterized command:

```bash
atlassian init jira \
  --deployment server \
  --url https://jira.example.com \
  --auth basic \
  --username "$ATLASSIAN_JIRA_USERNAME" \
  --password "$ATLASSIAN_JIRA_PASSWORD"

atlassian init confluence \
  --deployment server \
  --url https://confluence.example.com \
  --auth basic \
  --username "$ATLASSIAN_CONFLUENCE_USERNAME" \
  --password "$ATLASSIAN_CONFLUENCE_PASSWORD"
```

Use `atlassian init` for product credential sections. Configure dynamic headers
separately under `[headers]` or a concrete per-product section such as
`[jira.headers]`:

```toml
[headers]
Authorization = "Bearer $(example-token-helper)"
```

Product password and token values containing `$()` are stored without executing
the command. `${...}` references remain supported as environment placeholders.

Existing product config is not overwritten by default. Use `--force` when replacing a product block non-interactively:

```bash
atlassian init confluence --force --deployment server --url https://confluence.example.com --auth basic --username example-user --token secret
```

The default `~/.config/atlassian-cli/config.toml` file is still auto-created as a template on first product command when it does not already exist.

## Environment-Backed Config

For shared or automation-friendly setups, generate an environment-backed config template:

```bash
atlassian init jira --env-template
```

That writes commented placeholders you can keep in `config.toml` and fill through environment variables:

```toml
[jira]
deployment = "${ATLASSIAN_JIRA_DEPLOYMENT}"
url = "${ATLASSIAN_JIRA_URL}"
auth = "${ATLASSIAN_JIRA_AUTH}"
username = "${ATLASSIAN_JIRA_USERNAME}"
token = "${ATLASSIAN_JIRA_TOKEN}"

[jira.headers]
Authorization = "Bearer $(example-token-helper --host ${ATLASSIAN_JIRA_URL})"

[bitbucket]
deployment = "${ATLASSIAN_BITBUCKET_DEPLOYMENT}"
url = "${ATLASSIAN_BITBUCKET_URL}"
auth = "${ATLASSIAN_BITBUCKET_AUTH}"
token = "${ATLASSIAN_BITBUCKET_TOKEN}"

[bitbucket.headers]
Authorization = "Bearer $(example-token-helper --host ${ATLASSIAN_BITBUCKET_URL})"
```

Use `${...}` for environment-variable interpolation and `$(...)` for trusted local command substitution. In the example above, `${ATLASSIAN_JIRA_URL}` comes from your shell environment, while `$(example-token-helper --host ${ATLASSIAN_BITBUCKET_URL})` runs a local command after interpolation.

To inspect the resolved values that the CLI will use, run:

```bash
atlassian env
```

To load those exports into your current shell session:

```bash
eval "$(atlassian env)"
```

`atlassian env` prints shell-safe `export` lines for configured products and headers. This makes it easier to audit an environment-backed config before running product commands, and the CLI can consume exported header variables such as `ATLASSIAN_HEADER_X_REQUEST_SOURCE` or `ATLASSIAN_BITBUCKET_HEADER_AUTHORIZATION` directly on another machine without editing `config.toml`.

When `atlassian init --env-template` runs on a machine with a local `sshd` config, it also tries to add `AcceptEnv ATLASSIAN_*` so future SSH sessions can receive exported Atlassian variables. If the file cannot be updated directly, the command prints the manual `AcceptEnv` step and reload command instead.

On the SSH client side, add a matching `SendEnv` rule for any host that should receive those variables:

```sshconfig
Host example-host
  SendEnv ATLASSIAN_*
```

With both sides configured, you can export locally and connect with the same environment on the remote machine:

```bash
eval "$(atlassian env)"
ssh example-user@example-host
```

## Examples

- `atlassian jira issue get DEMO-1`
- `atlassian jira issue reparent-subtask DEMO-1234 --parent DEMO-1`
- `atlassian jira issue link types --name-filter clone`
- `atlassian jira issue link create --inward DEMO-1 --outward DEMO-1234 --type Cloners`
- `atlassian jira issue link list DEMO-1`
- `atlassian jira issue link delete LINK_ID --yes`
- `atlassian jira issue attachment list DEMO-1`
- `atlassian jira issue attachment upload DEMO-1 ./report.pdf`
- `atlassian jira issue attachment download DEMO-1 --name report.pdf --destination ./report.pdf`
- `atlassian jira user search --query example --project-key DEMO --limit 25`
- `atlassian jira field search --keyword story --limit 25`
- `atlassian jira field options customfield_10001 --project-key DEMO --issue-type Task --contains ready --return-limit 25`
- `atlassian confluence page get 1234`
- `atlassian confluence page attachment list 1234`
- `atlassian confluence page attachment upload 1234 ./diagram.png`
- `atlassian confluence page attachment download 1234 --name diagram.png --destination ./diagram.png`
- `atlassian bitbucket repo get DEMO example-repo`
- `atlassian bitbucket pr list DEMO example-repo`
- `atlassian bitbucket pr list -R DEMO/example-repo`
- `atlassian bitbucket pr list -R DEMO/example-repo --state DECLINED --limit 30`
- `atlassian bitbucket pr list -R DEMO/example-repo --json number,title,state,url`
- `atlassian bitbucket pr view 1234 -R DEMO/example-repo`
- `atlassian bitbucket pr view feature/DEMO-1234/example-change -R DEMO/example-repo`
- `atlassian bitbucket pr checks 1234 -R DEMO/example-repo`
- `atlassian bitbucket pr checks 1234 -R DEMO/example-repo --watch`
- `atlassian bitbucket pr checks 1234 -R DEMO/example-repo --json name,state,bucket,link`
- `atlassian bitbucket pr edit 1234 -R DEMO/example-repo --title "Example pull request"`
- `atlassian bitbucket pr edit feature/DEMO-1234/example-change --body "example response"`
- `atlassian bitbucket pr browse DEMO example-repo`
- `atlassian bitbucket pr diff DEMO example-repo 42`
- `atlassian bitbucket pr diff DEMO example-repo 42 --with-lines --output json`
- `atlassian bitbucket pr comment list DEMO example-repo 42`
- `atlassian bitbucket pr comment add DEMO example-repo 42 "example comment"`
- `atlassian bitbucket pr comment add DEMO example-repo 42 "example comment" --path example.py --line 12 --line-type ADDED`
- `atlassian bitbucket pr approve DEMO example-repo 42`
- `atlassian bitbucket pr unapprove DEMO example-repo 42`
- `atlassian bitbucket pr build-status DEMO example-repo 42`
- `atlassian bitbucket commit build-status abc123`

### Confluence attachment upload behavior

Confluence 6.12.4 attachment uploads accept exactly one source:

- Keep the compatible path forms: `atlassian confluence attachment upload DEMO --file "example response"` or `atlassian confluence page attachment upload DEMO "example response"`. The path basename becomes the attachment filename.
- Upload in-memory content with `atlassian confluence page attachment upload DEMO --content-base64 ZXhhbXBsZSByZXNwb25zZQ== --filename "example response" --comment "example comment" --minor-edit`.

`--filename` is required with `--content-base64`. `--minor-edit` controls watcher notification and defaults to `false`; use it when the attachment version should be recorded as a minor edit. Invalid base64 and conflicting or missing sources fail before upload.

`jira issue reparent-subtask` is limited to Jira Server 7.11.0 build 711000. It uses
Jira's authenticated Move Sub-task workflow and verifies the new parent after the
operation. Other Jira versions and builds fail before the workflow starts.

### Bitbucket API

`atlassian bitbucket api` is a generic authenticated REST command. Endpoint
paths are relative to `rest/api/1.0` unless they already begin with `rest/`.
Like `gh api`, adding `-f` or `-F` fields changes the default method to POST;
use `-X GET` when fields should become query parameters.

Compare two refs as structured JSON on Bitbucket Server 6.7.2:

```bash
atlassian bitbucket api -X GET \
  'projects/DEMO/repos/example-repo/compare/diff' \
  -f from='feature/DEMO-1234/example-change' \
  -f to='DEMO'
```

List every changed file or commit while filtering each Bitbucket page with jq:

```bash
atlassian bitbucket api -X GET --paginate --jq '.values[]' \
  'projects/DEMO/repos/example-repo/compare/changes' \
  -f from='feature/DEMO-1234/example-change' \
  -f to='DEMO'

atlassian bitbucket api -X GET --paginate --jq '.values[]' \
  'projects/DEMO/repos/example-repo/compare/commits' \
  -f from='feature/DEMO-1234/example-change' \
  -f to='DEMO'
```

The command returns the Bitbucket response body directly and does not add an
`--output` wrapper. Bitbucket Server 6.7.2 returns structured JSON from
`compare/diff`; it does not return unified diff text from that endpoint.
GraphQL, `--template`, and `--cache` are not implemented.

## Header injection

The CLI can accept externally generated HTTP headers without embedding OAuth logic.

Command-line example:

- `atlassian --url https://bitbucket.example.com --header 'Authorization: Bearer ...' bitbucket pr list DEMO example-repo`

Config file example:

```toml
[headers]
X-Request-Source = "example-cli"

[bitbucket]
deployment = "dc"
url = "https://bitbucket.example.com"
auth = "pat"

[bitbucket.headers]
Authorization = "Bearer $(example-token-helper)"
```

- `atlassian bitbucket pr list DEMO example-repo`

Config-backed header values may execute local shell commands through `$(...)`. Treat `~/.config/atlassian-cli/config.toml` as trusted local configuration.
Command substitution runs through `/bin/sh` on Unix-like systems and `cmd.exe` on Windows.
The default `~/.config/atlassian-cli/config.toml` file is auto-created as a template on first use.
Only top-level `[jira]`, `[confluence]`, `[bitbucket]`, and `[headers]` are supported.

## Output Modes

The CLI now uses `markdown` as the default human-readable output mode.

- Single-resource commands default to markdown detail output.
- Collection commands with browser support use it in a TTY and fall back to markdown summary output outside a TTY.
- Primary `bitbucket pr list` uses line-oriented output; use `bitbucket pr browse` for the interactive browser.
- Confluence page detail output renders storage HTML content into readable Markdown in `--output markdown`.
- Use `--output json` or `--output yaml` for normalized machine-readable output.
- Use `--output raw-json` to inspect the original provider response as JSON.
- Use `--output raw-yaml` to inspect the original provider response as YAML.
- Commands that compose multiple provider calls, such as `bitbucket pr build-status`,
  group the unnormalized provider payloads in raw output.

Examples:

- `atlassian jira issue get DEMO-1`
- `atlassian jira issue search --jql 'project = DEMO'`
- `atlassian confluence space list`
- `atlassian bitbucket pr list DEMO example-repo`
- `atlassian bitbucket pr diff DEMO example-repo 42`
- `atlassian bitbucket pr diff DEMO example-repo 42 --with-lines --output json`
- `atlassian bitbucket pr comment list DEMO example-repo 42`
- `atlassian bitbucket pr approve DEMO example-repo 42`
- `atlassian bitbucket pr unapprove DEMO example-repo 42`
- `atlassian bitbucket pr build-status DEMO example-repo 42`
- `atlassian bitbucket commit build-status abc123`
- `atlassian jira issue get DEMO-1 --output json`

### Jira issue read and update behavior

Jira Server 7.11 issue reads support the deployment-relevant `mcp-atlassian` controls:

- `--comment-limit 0..100` includes the newest requested comments; `0` omits comments.
- `--properties triage,ops` requests those issue properties.
- `--update-history false` reads the issue without updating the caller's view history.

`jira issue update --attachments '["./report.pdf"]'` updates ordinary fields first and then
uploads each file through Jira's attachment endpoint. Attachment paths are never inserted into
the issue fields payload. The dedicated `jira issue attachment upload` command remains available.

All update parts are optional and directly composable in one command: `--fields`,
`--additional-fields`, `--components`, `--attachments`, `--transition`, `--comment`,
`--comment-visibility`, `--worklog`, and `--worklog-started`. Description and comment text use
Markdown by default; use `--description-format jira` or `--comment-format jira` to preserve Jira
wiki markup.

```bash
atlassian jira issue update DEMO-1 \
  --fields '{"description":"## Example Page"}' \
  --comment "**example comment**" \
  --comment-visibility '{"type":"role","value":"reviewer-one"}' \
  --worklog 1m

atlassian jira issue assign DEMO-1 --assignee example-user-id
atlassian jira issue assign DEMO-1
atlassian jira issue transition DEMO-1 --transition-id 31 --comment "example response"
```

`jira issue assign` uses Jira's dedicated assignment API; omitting `--assignee` unassigns the
issue. Transition names and IDs are resolved against the issue's available transitions, and the
numeric ID is sent to Jira 7.11 with optional transition fields and comment.

### Jira user and field discovery

Jira Server 7.11 user search returns assignable users from the official
`user/assignable/search` API. Pass exactly one scope:

- `--project-key DEMO` searches users assignable in a project.
- `--issue-key DEMO-1` searches users assignable to one issue.
- `--query` is required and `--limit` caps the server response.

`jira field search` fetches the live field list on every call, accepts optional
`--keyword` (with `--query` retained as an alias), and applies `--limit` after matching.
Because there is no field cache, a separate refresh input is unnecessary.

`jira field options` reads Jira 7.11 create metadata for `--project-key` and
`--issue-type`. Use `--contains` for case-insensitive value/name matching and
`--return-limit` to cap matches; `--project` and `--limit` remain aliases.

### Jira issue create and batch-create behavior

Jira Server `7.11.0#711000-sha1:ff06e53` issue creation exposes the pinned
`mcp-atlassian` semantic inputs directly. Markdown is the default for `--description`; the CLI
converts headings, emphasis, lists, links, code, and pipe-delimited grids to Jira wiki markup before
creating the issue. Existing Jira-markup workflows can opt out of conversion with
`--description-format jira`.

```bash
atlassian jira issue create \
  --project-key DEMO \
  --issue-type Task \
  --summary "Example issue summary" \
  --assignee example-user-id \
  --description $'## Example Page\n\nexample response' \
  --components DEMO \
  --additional-fields '{"labels":["DEMO"]}'

atlassian jira issue create \
  --project-key DEMO \
  --issue-type Task \
  --summary "Example issue summary" \
  --description 'h2. Example Page' \
  --description-format jira
```

`jira issue batch-create --issues` accepts a JSON array of semantic objects. Each object requires
`project_key`, `summary`, and `issue_type`; `description`, `assignee`, and `components` are
optional, while remaining keys are treated as additional Jira fields. This corresponds to the
single-create `additional_fields` input. `--file` reads the same array from a JSON file.

```bash
atlassian jira issue batch-create \
  --issues '[{"project_key":"DEMO","summary":"Example issue summary","issue_type":"Task","description":"## Example Page","assignee":"example-user-id","components":["DEMO"],"labels":["DEMO"]}]'

atlassian jira issue batch-create \
  --issues '[{"project_key":"DEMO","summary":"Example issue summary","issue_type":"Task"}]' \
  --validate-only
```

`--validate-only` parses every semantic object and prepares its Jira fields without sending a Jira
mutation. A successful validation returns an empty `issues` list. Individual batch objects may set
`"description_format":"jira"` when their descriptions already contain Jira wiki markup.
Previously supported Jira REST-shaped objects using `project`, `issuetype`, and `summary` remain
accepted unchanged; their `description` is treated as Jira wiki markup. New callers should use the
semantic object shape above.

### Confluence page read and navigation

`confluence page get` accepts a numeric page ID, a full page URL containing a
`/pages/<id>/` path or `pageId` query, and a Confluence `/x/<tiny-id>` link. URL and tiny-link
selectors are resolved locally before the Confluence 6.12.4 content API is called.

```bash
atlassian confluence page get 1234
atlassian confluence page get 'https://confluence.example.com/pages/viewpage.action?pageId=1234'
atlassian confluence page get 'https://confluence.example.com/x/0gQ'
atlassian confluence page children 1234 --expand body.storage,version --limit 25 --start 0
atlassian confluence page tree DEMO --limit 100
```

Child-page reads expose Confluence 6.12.4 `expand`, `limit` (1-50), and zero-based `start`
pagination. Page-tree `--limit` is a global cap (1-1000) across the flattened breadth-first
result. Folder controls remain excluded because Confluence 6.12.4 child folders are not supported.

### Confluence page write input behavior

Confluence page create/update interprets semantic text as Markdown by default and converts it to
Confluence storage XHTML before writing. Pass exactly one of `--content/--body` or
`--content-file`; the file form reads UTF-8 text. Use `--content-format storage` as the explicit
raw escape hatch for caller-supplied storage XHTML.

```console
atlassian confluence page create --space-key DEMO --title "Example Page" --content "# Example Page"
atlassian confluence page create --space-key DEMO --title "Example Page" --content-file page.md --enable-heading-anchors
atlassian confluence page update 1234 --title "Example Page" --content "## Example Page" --parent-id 5678 --is-minor-edit --version-comment "example comment"
atlassian confluence page update 1234 --title "Example Page" --content-format storage --content "<p>example response</p>"
```

`--enable-heading-anchors` adds Confluence anchor macros while converting Markdown and is rejected
with storage input. `--parent-id`, `--is-minor-edit`, and `--version-comment` map to the documented
Confluence 6.12.4 page operations.

Confluence 6.12.4 accepts the official `version.minorEdit=true` update input but reports
`minorEdit=false` in the update response, page version, and independent history read-back. The CLI
therefore preserves the upstream request intent without claiming that this fixed version persists
a readable true value. Version creation and `--version-comment` remain independently readable.

Page `--emoji`, `--page-width`, and `--table-layout` are not established by the Confluence 6.12.4
API and fail before mutation. `--subtype` is Confluence Cloud-only and also fails before mutation.
Only `markdown` and `storage` are accepted by `--content-format` for this fixed-version boundary.

Page comments and replies use the same Markdown/storage contract:

```console
atlassian confluence comment add 1234 --body "**example comment**"
atlassian confluence comment reply 5678 --body "<p>example response</p>" --content-format storage
```

### Jira issue link behavior

Jira Server 7.11.0 manages issue links through dedicated REST resources. The CLI keeps
the Jira payload direction explicit: `--inward` maps to `inwardIssue`, and `--outward`
maps to `outwardIssue`.

- `atlassian jira issue link types --name-filter clone` filters available types by a case-insensitive name substring.
- `atlassian jira issue link create --inward DEMO-1 --outward DEMO-1234 --type Cloners --comment "example comment" --comment-visibility '{"type":"role","value":"reviewer-one"}'` creates a relationship with optional Jira comment visibility and reads it back before reporting success. Visibility accepts Jira `role` or enabled `group` restrictions.
- Repeating the same type and direction returns `status: existing` and `created: false`; it does not claim a second link was created.
- `atlassian jira issue link list DEMO-1 --output json` includes the link ID, type descriptions, both issue keys, linked issue summary, and direction relative to `DEMO-1`.
- `atlassian jira issue link delete LINK_ID --yes` deletes a link by ID and requires explicit confirmation.
- `--output raw-json` and `--output raw-yaml` preserve Jira responses. Because create performs type discovery, duplicate preflight, and read-back, its raw output groups those responses in one object.

This command group targets Atlassian Jira Project Management Software
`7.11.0#711000-sha1:ff06e53` on Server/Data Center. Jira Cloud is out of scope.

### Bitbucket pull request reads and checks

`pr list` is line-oriented and defaults to Bitbucket state `OPEN` with a limit of 30. `--state` accepts the native `OPEN`, `DECLINED`, `MERGED`, and `ALL` values case-insensitively and preserves native state names in output. Repositories may be supplied as `PROJECT_KEY REPO_SLUG`, with `-R PROJECT_KEY/REPO_SLUG`, through `ATLASSIAN_BITBUCKET_REPO=DEMO/example-repo`, or from local Git context. `--web` conflicts with `--json`. Base JSON field selection is available without `--jq` or `--template` in this phase.

On Bitbucket Server 6.7.2, the parser recognizes `reviews` and `latestReviews` but reports the B30 capability failure, `mergeCommit` reports B31, and `potentialMergeCommit` reports B25.

`pr checks` resolves the pull request with the same number, URL, branch, and current-branch rules as `pr view`. It reads build statuses only from the pull request head commit. Human output uses exit `0` when all checks pass, exit `1` when any check fails, and exit `8` while checks are pending. `--watch` polls the current PR head until checks finish, and `--fail-fast` stops on the first failure. JSON output selects from `bucket`, `completedAt`, `description`, `event`, `link`, `name`, `startedAt`, `state`, and `workflow`, and exits `0` after a successful read regardless of check state.

`--required` is unavailable on Bitbucket Server 6.7.2 because its build-status records do not identify individual required checks. `--jq` and `--template` remain deferred to the shared gh-compatible formatter phase.

`pr edit` accepts the same number, URL, branch, and current-branch selectors as `gh pr edit`. It can update the title, body, destination branch, and individual reviewers. Bitbucket pull requests do not have GitHub-equivalent assignees, labels, projects, and milestones, so those flags are not registered. Without edit flags, a TTY prompts for supported fields; non-interactive use requires an explicit edit flag. Successful edits print only the pull request URL.

| Workflow | Current behavior |
| --- | --- |
| `pr list PROJECT REPO` | Preserved; `pr list -R PROJECT/REPO` is also supported |
| `pr build-status PROJECT REPO ID --latest-only` | `pr checks ID -R PROJECT/REPO` |
| Full-screen `pr list PROJECT REPO` | `pr browse PROJECT REPO` |
| Existing `pr list --output MODE` | Remains a hidden, deprecated D06 compatibility input |
| `get`, `build-status`, `approve`, and `unapprove` | Remain callable compatibility commands |
| Existing detailed exits | Migrated primary reads use exits `0`, `1`, `2`, and `4` |

`pr browse` preserves the full-screen browser in a TTY and its static Markdown fallback outside a TTY.

### Interactive browser behavior

TTY collection commands that support interactive browsing open a compact browser instead of printing a long static list. For pull requests, use `pr browse`.

- The top region is a dense single-line-per-item list for fast scanning.
- The bottom preview is a live preview that shows metadata for the selected item without opening full detail.
- `Enter` opens the full markdown detail view for the selected item.
- Bitbucket pull request detail lazily loads the textual diff when you open detail.
- Detail view supports scrolling with `j/k`, arrow keys, and `PageUp/PageDown`.
- `b` or `Esc` returns from detail to the list.
- `/` filters only the items already loaded into the current browser session.
- `r` refreshes the first page and returns the browser to list mode.

Keybindings:

`j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit`

Bitbucket pull request diff behavior:

- `atlassian bitbucket pr diff DEMO example-repo 42` shows ANSI-colored diff output in a TTY.
- The same command falls back to plain text when redirected or piped.
- `atlassian bitbucket pr diff DEMO example-repo 42 --with-lines --output json` returns line-aware diff output with old and new line coordinates and reusable inline-comment anchors.

Bitbucket pull request comments and build status behavior:

- `atlassian bitbucket pr checks 1234 -R DEMO/example-repo` shows gh-compatible checks for the pull request head commit.
- `atlassian bitbucket pr checks 1234 -R DEMO/example-repo --watch` polls until the head checks finish.
- `atlassian bitbucket pr checks 1234 -R DEMO/example-repo --json name,state,bucket,link` returns selected check fields for automation.
- `atlassian bitbucket pr comment list DEMO example-repo 42` lists pull request comments.
- `atlassian bitbucket pr comment add DEMO example-repo 42 "example comment" --path example.py --line 12 --line-type ADDED` creates an inline pull request comment.
- `atlassian bitbucket pr comment edit DEMO example-repo 42 1001 "example comment" --version 3` requires the current comment version.
- `atlassian bitbucket pr approve DEMO example-repo 42` approves a pull request as the authenticated user.
- `atlassian bitbucket pr unapprove DEMO example-repo 42` removes the authenticated user's pull request approval.
- `atlassian bitbucket pr build-status DEMO example-repo 42` summarizes build statuses for pull request commits.
- `atlassian bitbucket pr build-status DEMO example-repo 42 --latest-only` checks only the pull request head commit.
- `atlassian bitbucket commit build-status abc123` checks a specific commit.

## Scope

The CLI now covers the `mcp-atlassian` `TOOLSETS=default` Jira and Confluence command groups for Server/Data Center:

- Jira issues, issue links, fields, comments, attachments, and transitions
- Confluence pages, comments, and attachments

Normalized json and yaml output now follows MCP-style resource envelopes more closely. This is a breaking change for scripts that consumed older normalized output.

Raw modes with unchanged behavior:

- `raw-json`
- `raw-yaml`

One default MCP capability remains explicitly unsupported in CLI v1: Jira batch changelog fetch. That workflow depends on Cloud support, and the current CLI still rejects `--deployment cloud`.

## Contributing

Contributor workflows, including local setup, smoke tests, live e2e execution, CI/release notes, and maintenance checklists, are documented in [CONTRIBUTING.md](CONTRIBUTING.md).
