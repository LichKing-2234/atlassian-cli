from pathlib import Path


def test_readme_mentions_markdown_default_and_interactive_lists() -> None:
    readme = Path("README.md").read_text()

    assert "markdown" in readme
    assert "interactive" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme
    assert "table" not in readme


def test_readme_mentions_interactive_preview_browser() -> None:
    readme = Path("README.md").read_text()

    assert "live preview" in readme.lower()
    assert "j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit" in readme
    assert "bottom preview" in readme.lower()
    assert "supports scrolling" in readme.lower()


def test_readme_mentions_bitbucket_pr_diff_tty_behavior() -> None:
    readme = Path("README.md").read_text()

    assert "bitbucket pr diff demo example-repo 42" in readme.lower()
    assert "bitbucket pr diff demo example-repo 42 --with-lines" in readme.lower()
    assert "ansi-colored diff output in a tty" in readme.lower()
    assert "falls back to plain text" in readme.lower()
    assert "line-aware diff output" in readme.lower()


def test_readme_documents_bitbucket_api_compare_endpoints() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    for value in (
        "atlassian bitbucket api -X GET",
        "projects/DEMO/repos/example-repo/compare/diff",
        "projects/DEMO/repos/example-repo/compare/changes",
        "projects/DEMO/repos/example-repo/compare/commits",
        "--paginate --jq '.values[]'",
        "structured JSON",
    ):
        assert value in readme


def test_readme_mentions_bitbucket_comments_and_build_status() -> None:
    readme = Path("README.md").read_text()

    assert "bitbucket pr comment list demo example-repo 42" in readme.lower()
    assert (
        'bitbucket pr comment add demo example-repo 42 "example comment" --path example.py'
        in readme.lower()
    )
    assert "bitbucket pr build-status demo example-repo 42" in readme.lower()
    assert "bitbucket commit build-status abc123" in readme.lower()


def test_readme_documents_gh_compatible_pr_reads_and_browser_migration() -> None:
    readme = Path("README.md").read_text()

    assert "atlassian bitbucket pr list DEMO example-repo" in readme
    assert "atlassian bitbucket pr list -R DEMO/example-repo" in readme
    assert "atlassian bitbucket pr view 1234 -R DEMO/example-repo" in readme
    assert "atlassian bitbucket pr browse DEMO example-repo" in readme
    assert "`pr list` is line-oriented" in readme
    assert "`pr browse` preserves the full-screen browser" in readme
    assert "Bitbucket Server 6.7.2" in readme
    assert "B25" in readme
    assert "B30" in readme
    assert "B31" in readme
    for state in ("OPEN", "DECLINED", "MERGED", "ALL"):
        assert state in readme
    assert "Its `closed` state maps" not in readme


def test_readme_mentions_full_local_e2e_suite() -> None:
    readme = Path("README.md").read_text()
    contributing = Path("CONTRIBUTING.md").read_text()

    assert "CONTRIBUTING.md" in readme
    assert "tests/e2e/test_jira_live.py" in contributing
    assert "tests/e2e/test_confluence_live.py" in contributing
    assert "tests/e2e/test_bitbucket_live.py" in contributing
    assert "ATLASSIAN_E2E=1" in contributing
    assert "ATLASSIAN_E2E_JIRA_PROJECT" in contributing
    assert "ATLASSIAN_E2E_CONFLUENCE_SPACE" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_PROJECT" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_CREATE_PROJECT" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_REPO" in contributing
    assert "real writes" in contributing.lower()


def test_readme_mentions_semantic_alignment_and_output_breaking_change() -> None:
    readme = Path("README.md").read_text()

    assert "TOOLSETS=default" in readme
    assert (
        "normalized json and yaml output now follows mcp-style resource envelopes" in readme.lower()
    )
    assert "raw-json" in readme
    assert "raw-yaml" in readme


def test_readme_mentions_init_command() -> None:
    readme = Path("README.md").read_text()
    normalized_readme = " ".join(readme.lower().split())

    assert "atlassian init" in readme
    assert "atlassian init jira" in readme
    assert "atlassian init --help" in readme
    assert "--force" in readme
    assert "product password and token values containing `$()`" in normalized_readme
    assert "stored without executing the command" in normalized_readme
    assert "[jira.headers]" in normalized_readme
    assert "use `atlassian init` for product credential sections" in normalized_readme


def test_readme_mentions_env_backed_config_workflow() -> None:
    readme = Path("README.md").read_text()

    assert "${ATLASSIAN_JIRA_URL}" in readme
    assert "atlassian init jira --env-template" in readme
    assert 'eval "$(atlassian env)"' in readme
    assert "environment-backed config" in readme.lower()
    assert (
        'Authorization = "Bearer $(example-token-helper --host ${ATLASSIAN_BITBUCKET_URL})"'
        in readme
    )
    assert "ATLASSIAN_HEADER_X_REQUEST_SOURCE" in readme
    assert "ATLASSIAN_BITBUCKET_HEADER_AUTHORIZATION" in readme
    assert "AcceptEnv ATLASSIAN_*" in readme
    assert "SendEnv ATLASSIAN_*" in readme


def test_readme_mentions_version_flag() -> None:
    readme = Path("README.md").read_text()

    assert "atlassian --version" in readme


def test_readme_mentions_uv_tool_install_from_release_assets() -> None:
    readme = Path("README.md").read_text()

    assert "uv tool install" in readme
    assert ".whl" in readme
    assert "GitHub Release" in readme


def test_readme_scopes_update_install_to_binary_installs() -> None:
    readme = Path("README.md").read_text().lower()

    assert "binary install" in readme
    assert "atlassian update install" in readme
    assert "package-managed installs" in readme
    assert "shows the installer's live download progress" in readme
    assert "suppresses replayed progress noise" in readme


def test_readme_mentions_pyoxidizer_backed_binary_release_path() -> None:
    readme = Path("README.md").read_text().lower()

    assert "pyoxidizer" in readme


def test_readme_mentions_package_managers_should_upgrade_package_installs() -> None:
    readme = Path("README.md").read_text().lower()

    assert "uv tool upgrade" in readme


def test_contributing_mentions_new_live_e2e_env_overrides() -> None:
    contributing = Path("CONTRIBUTING.md").read_text()

    assert "ATLASSIAN_E2E_JIRA_ISSUE_TYPE" in contributing
    assert "ATLASSIAN_E2E_CONFLUENCE_PARENT_PAGE" in contributing
    assert "ATLASSIAN_E2E_BITBUCKET_EXISTING_REPO" in contributing
