import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlassian_cli.core.errors import AtlassianCliError
from atlassian_cli.products.bitbucket.gh_compat.pr_output import (
    JSON_FIELDS,
    MISSING_JSON_VALUE,
    GhPreflightError,
    render_json,
    render_pr_list,
    render_pr_view,
    validate_json_fields,
)

CONTRACT_PATH = Path(__file__).parents[2] / "fixtures/gh-v2.96.0/bitbucket-pr-read-contract.json"
NOW = datetime(2026, 7, 16, 12, tzinfo=UTC)


@pytest.fixture
def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text())


@pytest.fixture
def canonical_pr() -> dict:
    return {
        "additions": 1,
        "author": {
            "id": "example-user-id",
            "is_bot": False,
            "login": "~example-user",
            "name": "Example Author",
        },
        "baseRefName": "main",
        "body": "example response",
        "comments": [
            {
                "id": "DEMO-1234",
                "url": "",
                "body": "example comment",
                "author": {
                    "id": "example-user-id",
                    "is_bot": False,
                    "login": "reviewer-one",
                    "name": "Example Collaborator",
                },
                "authorAssociation": "NONE",
                "createdAt": "2026-07-15T12:00:00Z",
                "updatedAt": "2026-07-15T12:00:00Z",
            }
        ],
        "commits": [{}],
        "createdAt": "2026-07-15T12:00:00Z",
        "deletions": 0,
        "headRefName": "feature/DEMO-1234/example-change",
        "number": 1234,
        "reviewRequests": [
            {
                "id": "example-user-id",
                "is_bot": False,
                "login": "reviewer-one",
                "name": "Example Collaborator",
            }
        ],
        "state": "OPEN",
        "statusCheckRollup": [],
        "title": "Example pull request",
        "url": (
            "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"
        ),
    }


def strip_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", value)


def test_json_fields_match_pinned_contract(contract: dict) -> None:
    assert list(JSON_FIELDS) == contract["json_fields"]
    assert len(JSON_FIELDS) == 36


def test_json_without_value_lists_sorted_fields() -> None:
    with pytest.raises(GhPreflightError) as exc:
        validate_json_fields(MISSING_JSON_VALUE, web=False, surface="pr list")

    message = str(exc.value)
    assert message.startswith("Specify one or more comma-separated fields for `--json`:\n")
    assert "  additions\n  author\n" in message
    assert message.splitlines()[1:] == [f"  {field}" for field in sorted(JSON_FIELDS)]


def test_web_json_conflict_precedes_field_validation() -> None:
    with pytest.raises(GhPreflightError, match="cannot use `--web` with `--json`"):
        validate_json_fields("unknownField", web=True, surface="pr list")


def test_omitted_json_does_not_conflict_with_web() -> None:
    assert validate_json_fields(None, web=True, surface="pr list") is None
    assert validate_json_fields([], web=True, surface="pr list") is None


def test_unknown_field_lists_available_fields() -> None:
    with pytest.raises(GhPreflightError) as exc:
        validate_json_fields("unknownField", web=False, surface="pr view")

    message = str(exc.value)
    assert message.startswith('Unknown JSON field: "unknownField"\nAvailable fields:\n')
    assert message.splitlines()[2:] == [f"  {field}" for field in sorted(JSON_FIELDS)]


@pytest.mark.parametrize(
    ("field", "code", "capability"),
    [
        ("latestReviews", "B30", "atomic pull-request review records"),
        ("reviews", "B30", "atomic pull-request review records"),
        ("mergeCommit", "B31", "pull-request merge-commit identity"),
        ("potentialMergeCommit", "B25", "potential merge commit"),
    ],
)
def test_blocked_field_is_accepted_then_fails_capability_preflight(
    field: str, code: str, capability: str
) -> None:
    expected = (
        f"unsupported by Bitbucket Server 6.7.2: {capability} ({code}); "
        f"required by gh v2.96.0 pr view --json {field}"
    )
    with pytest.raises(GhPreflightError, match=re.escape(expected)):
        validate_json_fields(field, web=False, surface="pr view")


def test_repeated_and_comma_separated_fields_are_deduplicated_in_order() -> None:
    assert validate_json_fields(
        ["number,title", "number", "state,title"],
        web=False,
        surface="pr list",
    ) == ("number", "title", "state")


def test_non_tty_json_is_compact_sorted_and_newline_terminated() -> None:
    value = {"title": "Example pull request", "number": 1234}
    assert render_json(value, color=False) == ('{"number":1234,"title":"Example pull request"}\n')


def test_tty_json_matches_gh_jsoncolor() -> None:
    assert render_json({"number": 1234}, color=True) == (
        '\x1b[1;37m{\x1b[m\n  \x1b[1;34m"number"\x1b[m\x1b[1;37m:\x1b[m 1234\n\x1b[1;37m}\x1b[m\n'
    )


def test_tty_json_recursively_colors_values_and_sorts_keys() -> None:
    assert render_json(
        {"string": "example response", "array": [True, None, 1]},
        color=True,
    ) == (
        "\x1b[1;37m{\x1b[m\n"
        '  \x1b[1;34m"array"\x1b[m\x1b[1;37m:\x1b[m '
        "\x1b[1;37m[\x1b[m\n"
        "    \x1b[33mtrue\x1b[m\x1b[1;37m,\x1b[m\n"
        "    \x1b[36mnull\x1b[m\x1b[1;37m,\x1b[m\n"
        "    1\n"
        "  \x1b[1;37m]\x1b[m\x1b[1;37m,\x1b[m\n"
        '  \x1b[1;34m"string"\x1b[m\x1b[1;37m:\x1b[m '
        '\x1b[32m"example response"\x1b[m\n'
        "\x1b[1;37m}\x1b[m\n"
    )


def test_tty_json_colors_empty_delimiters_separately_like_gh() -> None:
    assert render_json({"array": [], "object": {}}, color=True) == (
        "\x1b[1;37m{\x1b[m\n"
        '  \x1b[1;34m"array"\x1b[m\x1b[1;37m:\x1b[m '
        "\x1b[1;37m[\x1b[m\x1b[1;37m]\x1b[m\x1b[1;37m,\x1b[m\n"
        '  \x1b[1;34m"object"\x1b[m\x1b[1;37m:\x1b[m '
        "\x1b[1;37m{\x1b[m\x1b[1;37m}\x1b[m\n"
        "\x1b[1;37m}\x1b[m\n"
    )


def test_list_non_tty_matches_golden(contract: dict, canonical_pr: dict) -> None:
    assert (
        render_pr_list(
            [canonical_pr],
            repository="DEMO/example-repo",
            total=1,
            filtered=False,
            tty=False,
            color=False,
            now=NOW,
        )
        == contract["golden"]["list_non_tty"]
    )


def test_list_tty_matches_golden(contract: dict, canonical_pr: dict) -> None:
    assert (
        strip_ansi(
            render_pr_list(
                [canonical_pr],
                repository="DEMO/example-repo",
                total=1,
                filtered=False,
                tty=True,
                color=True,
                now=NOW,
            )
        )
        == contract["golden"]["list_tty"]
    )


def test_list_tty_colors_state_id_branch_and_created_time(canonical_pr: dict) -> None:
    rendered = render_pr_list(
        [canonical_pr],
        repository="DEMO/example-repo",
        total=1,
        filtered=False,
        tty=True,
        color=True,
        now=NOW,
    )

    assert "\x1b[32m#1234\x1b[0m" in rendered
    assert "\x1b[36mfeature/DEMO-1234/example-change\x1b[0m" in rendered
    assert "\x1b[2mabout 1 day ago\x1b[0m" in rendered


@pytest.mark.parametrize(
    ("filtered", "message"),
    [
        (False, "no open pull requests in DEMO/example-repo"),
        (True, "no pull requests match your search in DEMO/example-repo"),
    ],
)
def test_empty_list_raises_exact_no_results_error(filtered: bool, message: str) -> None:
    with pytest.raises(AtlassianCliError, match=f"^{re.escape(message)}$"):
        render_pr_list(
            [],
            repository="DEMO/example-repo",
            total=0,
            filtered=filtered,
            tty=True,
            color=False,
            now=NOW,
        )


def test_list_collapses_title_whitespace(canonical_pr: dict) -> None:
    canonical_pr["title"] = "  Example\n  pull   request  "
    rendered = render_pr_list(
        [canonical_pr],
        repository="DEMO/example-repo",
        total=1,
        filtered=False,
        tty=False,
        color=False,
        now=NOW,
    )
    assert "\tExample pull request\t" in rendered


def test_view_non_tty_matches_golden(contract: dict, canonical_pr: dict) -> None:
    assert (
        render_pr_view(
            canonical_pr,
            repository="DEMO/example-repo",
            tty=False,
            color=False,
            comments=False,
            now=NOW,
        )
        == contract["golden"]["view_non_tty"]
    )


def test_view_comments_non_tty_outputs_only_raw_comments(
    contract: dict, canonical_pr: dict
) -> None:
    assert (
        render_pr_view(
            canonical_pr,
            repository="DEMO/example-repo",
            tty=False,
            color=False,
            comments=True,
            now=NOW,
        )
        == contract["golden"]["view_comments_non_tty"]
    )


def test_view_tty_contains_pinned_human_sections(canonical_pr: dict) -> None:
    rendered = strip_ansi(
        render_pr_view(
            canonical_pr,
            repository="DEMO/example-repo",
            tty=True,
            color=True,
            comments=False,
            now=NOW,
            width=80,
        )
    )

    assert rendered.startswith("Example pull request DEMO/example-repo#1234\n")
    assert (
        "Open • Example Author wants to merge 1 commit into main from "
        "feature/DEMO-1234/example-change • about 1 day ago\n"
    ) in rendered
    assert "+1 -0 • No checks\n" in rendered
    assert "Reviewers: reviewer-one (Requested)\n" in rendered
    assert "\nexample response\n" in rendered
    assert "example comment" in rendered
    assert rendered.endswith(
        "View this pull request in Bitbucket: "
        "https://bitbucket.example.com/projects/DEMO/repos/"
        "example-repo/pull-requests/1234\n"
    )


def test_view_tty_renders_markdown_body_at_injected_width(canonical_pr: dict) -> None:
    canonical_pr["body"] = "**example response** with enough words to wrap"
    rendered = render_pr_view(
        canonical_pr,
        repository="DEMO/example-repo",
        tty=True,
        color=True,
        comments=False,
        now=NOW,
        width=24,
    )

    assert "\x1b[1mexample response\x1b[0m" in rendered
    assert "example response with\nenough words to wrap" in strip_ansi(rendered)


def test_view_tty_comment_preview_shows_only_latest_unless_requested(
    canonical_pr: dict,
) -> None:
    earlier = deepcopy(canonical_pr["comments"][0])
    earlier.update(
        {
            "id": "DEMO-1",
            "body": "older example comment",
            "createdAt": "2026-07-14T12:00:00Z",
            "updatedAt": "2026-07-14T12:00:00Z",
        }
    )
    canonical_pr["comments"].insert(0, earlier)

    preview = strip_ansi(
        render_pr_view(
            canonical_pr,
            repository="DEMO/example-repo",
            tty=True,
            color=True,
            comments=False,
            now=NOW,
        )
    )
    full = strip_ansi(
        render_pr_view(
            canonical_pr,
            repository="DEMO/example-repo",
            tty=True,
            color=True,
            comments=True,
            now=NOW,
        )
    )

    assert "older example comment" not in preview
    assert "example comment" in preview
    assert full.index("older example comment") < full.index("example comment")


@pytest.mark.parametrize(
    ("state", "display"),
    [
        ("APPROVED", "Approved"),
        ("NEEDS_WORK", "Changes requested"),
        ("UNAPPROVED", "Requested"),
    ],
)
def test_view_maps_bitbucket_reviewer_states(canonical_pr: dict, state: str, display: str) -> None:
    canonical_pr["reviewRequests"][0]["status"] = state

    rendered = strip_ansi(
        render_pr_view(
            canonical_pr,
            repository="DEMO/example-repo",
            tty=True,
            color=True,
            comments=False,
            now=NOW,
        )
    )
    assert f"reviewer-one ({display})" in rendered


@pytest.mark.parametrize(
    ("checks", "summary"),
    [
        ([{"state": "SUCCESS"}], "✓ Checks passing"),
        ([{"state": "PENDING"}], "- Checks pending"),
        ([{"state": "FAILURE"}], "× All checks failing"),
    ],
)
def test_view_summarizes_checks(canonical_pr: dict, checks: list[dict], summary: str) -> None:
    canonical_pr["statusCheckRollup"] = checks

    rendered = strip_ansi(
        render_pr_view(
            canonical_pr,
            repository="DEMO/example-repo",
            tty=True,
            color=True,
            comments=False,
            now=NOW,
        )
    )
    assert summary in rendered
