import re

import pytest

from atlassian_cli.products.bitbucket.gh_compat.pr_checks import (
    CHECK_FIELDS,
    checks_exit_code,
    project_checks,
    render_checks,
    select_check_fields,
)


def _build(
    state: str,
    *,
    key: str = "DEMO-1234",
    name: str = "Example pull request",
    url: str = "https://bitbucket.example.com/example-response",
    description: str = "example response",
) -> dict:
    return {
        "key": key,
        "name": name,
        "state": state,
        "url": url,
        "description": description,
    }


def test_check_fields_match_gh_v2_96() -> None:
    assert CHECK_FIELDS == (
        "bucket",
        "completedAt",
        "description",
        "event",
        "link",
        "name",
        "startedAt",
        "state",
        "workflow",
    )


@pytest.mark.parametrize(
    ("provider_state", "state", "bucket"),
    [
        ("SUCCESSFUL", "SUCCESS", "pass"),
        ("FAILED", "FAILURE", "fail"),
        ("INPROGRESS", "PENDING", "pending"),
    ],
)
def test_project_checks_maps_bitbucket_status_contexts(
    provider_state: str,
    state: str,
    bucket: str,
) -> None:
    assert project_checks([_build(provider_state)]) == [
        {
            "bucket": bucket,
            "completedAt": "0001-01-01T00:00:00Z",
            "description": "example response",
            "event": "",
            "link": "https://bitbucket.example.com/example-response",
            "name": "Example pull request",
            "startedAt": "0001-01-01T00:00:00Z",
            "state": state,
            "workflow": "",
        }
    ]


def test_project_checks_falls_back_to_key_and_sorts_by_bucket_name_and_link() -> None:
    checks = project_checks(
        [
            _build("SUCCESSFUL", name="reviewer-two", url="https://example.com/z"),
            _build("INPROGRESS", name="", key="reviewer-one"),
            _build("FAILED", name="reviewer-two", url="https://example.com/b"),
            _build("FAILED", name="reviewer-two", url="https://example.com/a"),
        ]
    )

    assert [(item["bucket"], item["name"], item["link"]) for item in checks] == [
        ("fail", "reviewer-two", "https://example.com/a"),
        ("fail", "reviewer-two", "https://example.com/b"),
        ("pending", "reviewer-one", "https://bitbucket.example.com/example-response"),
        ("pass", "reviewer-two", "https://example.com/z"),
    ]


@pytest.mark.parametrize(
    ("states", "exit_code"),
    [
        (["SUCCESSFUL"], 0),
        (["SUCCESSFUL", "FAILED"], 1),
        (["SUCCESSFUL", "INPROGRESS"], 8),
        (["FAILED", "INPROGRESS"], 1),
    ],
)
def test_checks_exit_code_matches_gh(states: list[str], exit_code: int) -> None:
    assert checks_exit_code(project_checks([_build(state) for state in states])) == exit_code


def test_select_check_fields_projects_each_check() -> None:
    checks = project_checks([_build("FAILED")])

    assert select_check_fields(checks, ("name", "state", "bucket", "link")) == [
        {
            "name": "Example pull request",
            "state": "FAILURE",
            "bucket": "fail",
            "link": "https://bitbucket.example.com/example-response",
        }
    ]


def test_non_tty_checks_are_headerless_tsv_with_zero_elapsed_time() -> None:
    checks = project_checks(
        [
            _build("SUCCESSFUL", name="reviewer-two", description=""),
            _build("FAILED", name="reviewer-one"),
            _build("INPROGRESS", name="reviewer-three", description=""),
        ]
    )

    assert render_checks(checks, tty=False, color=False, width=80) == (
        "reviewer-one\tfail\t0\thttps://bitbucket.example.com/example-response\t"
        "example response\n"
        "reviewer-three\tpending\t0\thttps://bitbucket.example.com/example-response\t\n"
        "reviewer-two\tpass\t0\thttps://bitbucket.example.com/example-response\t\n"
    )


def test_tabular_checks_collapse_provider_control_whitespace() -> None:
    checks = project_checks(
        [
            _build(
                "FAILED",
                name="Example\npull\trequest",
                description="example\r\n response",
                url="https://bitbucket.example.com/\nexample-response",
            )
        ]
    )

    non_tty = render_checks(checks, tty=False, color=False, width=120)
    tty = render_checks(checks, tty=True, color=False, width=120)

    assert non_tty == (
        "Example pull request\tfail\t0\t"
        "https://bitbucket.example.com/ example-response\texample response\n"
    )
    assert "Example pull request" in tty
    assert "example response" in tty
    assert "https://bitbucket.example.com/ example-response" in tty


def test_tty_checks_include_summary_tallies_symbols_and_table() -> None:
    checks = project_checks(
        [
            _build("SUCCESSFUL", name="reviewer-two", description=""),
            _build("FAILED", name="reviewer-one"),
            _build("INPROGRESS", name="reviewer-three", description=""),
        ]
    )

    rendered = render_checks(checks, tty=True, color=False, width=120)
    lines = rendered.splitlines()

    assert lines[:3] == [
        "Some checks were not successful",
        "0 cancelled, 1 failing, 1 successful, 0 skipped, and 1 pending checks",
        "",
    ]
    assert lines[3].split() == ["NAME", "DESCRIPTION", "ELAPSED", "URL"]
    assert [re.split(r"\s{2,}", line.strip())[0] for line in lines[4:]] == ["X", "*", "✓"]
    assert [
        name in line
        for name, line in zip(
            ("reviewer-one", "reviewer-three", "reviewer-two"), lines[4:], strict=True
        )
    ] == [True, True, True]


def test_tty_checks_apply_gh_status_colors() -> None:
    rendered = render_checks(
        project_checks([_build("FAILED")]),
        tty=True,
        color=True,
        width=120,
    )

    assert "\x1b[31mX\x1b[0m" in rendered
