import pytest

from atlassian_cli.products.jira.visibility import parse_visibility


@pytest.mark.parametrize("visibility_type", ["role", "group"])
def test_parse_visibility_accepts_jira_core_shapes(visibility_type: str) -> None:
    assert parse_visibility(
        f'{{"type":"{visibility_type}","value":"reviewer-one"}}',
        option_name="--comment-visibility",
    ) == {"type": visibility_type, "value": "reviewer-one"}


@pytest.mark.parametrize(
    "value",
    ["[]", '{"type":"public","value":"reviewer-one"}', '{"type":"role","value":""}'],
)
def test_parse_visibility_rejects_non_core_or_incomplete_shapes(value: str) -> None:
    with pytest.raises(ValueError):
        parse_visibility(value, option_name="--comment-visibility")
