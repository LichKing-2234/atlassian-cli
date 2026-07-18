from io import StringIO

import pytest

from atlassian_cli.products.bitbucket.api_fields import parse_api_fields


def resolve(name: str) -> str:
    return {
        "project": "DEMO",
        "repo": "example-repo",
        "branch": "feature/DEMO-1234/example-change",
    }[name]


def test_parse_api_fields_keeps_raw_values_and_converts_typed_values() -> None:
    result = parse_api_fields(
        ["raw=true"],
        [
            "count=42",
            "enabled=true",
            "disabled=false",
            "missing=null",
            "repo={repo}",
        ],
        resolver=resolve,
        stdin=StringIO(""),
    )

    assert result == {
        "raw": "true",
        "count": 42,
        "enabled": True,
        "disabled": False,
        "missing": None,
        "repo": "example-repo",
    }


def test_parse_api_fields_expands_all_supported_placeholders() -> None:
    result = parse_api_fields(
        [],
        [
            "project={project}",
            "repo={repo}",
            "branch={branch}",
        ],
        resolver=resolve,
        stdin=StringIO(""),
    )

    assert result == {
        "project": "DEMO",
        "repo": "example-repo",
        "branch": "feature/DEMO-1234/example-change",
    }


def test_parse_api_fields_rejects_unknown_placeholder() -> None:
    with pytest.raises(ValueError, match="unknown placeholder: owner"):
        parse_api_fields([], ["value={owner}"], resolver=resolve, stdin=StringIO(""))


def test_parse_api_fields_builds_nested_objects_and_arrays() -> None:
    result = parse_api_fields(
        [],
        [
            "properties[][property_name]=DEMO",
            "properties[][allowed_values][]=DEMO-1",
            "properties[][allowed_values][]=DEMO-1234",
            "empty[]=",
        ],
        resolver=resolve,
        stdin=StringIO(""),
    )

    assert result == {
        "properties": [
            {
                "property_name": "DEMO",
                "allowed_values": ["DEMO-1", "DEMO-1234"],
            }
        ],
        "empty": [""],
    }


def test_parse_api_fields_accepts_empty_array_declaration() -> None:
    assert parse_api_fields(
        ["reviewers[]"],
        [],
        resolver=resolve,
        stdin=StringIO(""),
    ) == {"reviewers": []}


def test_parse_api_fields_keeps_typed_null_inside_array() -> None:
    assert parse_api_fields(
        [],
        ["reviewers[]=null"],
        resolver=resolve,
        stdin=StringIO(""),
    ) == {"reviewers": [None]}


def test_parse_api_fields_reads_typed_file_and_stdin_values(tmp_path) -> None:
    value_file = tmp_path / "value.txt"
    value_file.write_text("example response", encoding="utf-8")

    result = parse_api_fields(
        [],
        [f"file=@{value_file}", "stdin=@-"],
        resolver=resolve,
        stdin=StringIO("example response"),
    )

    assert result == {
        "file": "example response",
        "stdin": "example response",
    }


@pytest.mark.parametrize(
    ("raw_fields", "typed_fields", "message"),
    [
        (["value"], [], "invalid key"),
        (["value[name]"], [], "requires a value separated by an '=' sign"),
        (["=example response"], [], "invalid key"),
        (["value=example response"], ["value=42"], "unexpected override"),
        (["value=example response"], ["value[name]=DEMO"], "expected map"),
        (["value[]=example response"], ["value[name]=DEMO"], "expected map"),
        (["value[]junk=example response"], [], "invalid key"),
        (["value[name]junk=example response"], [], "invalid key"),
        (["value[name=example response"], [], "invalid key"),
        (["value]name[=example response"], [], "invalid key"),
    ],
)
def test_parse_api_fields_rejects_invalid_or_conflicting_fields(
    raw_fields: list[str],
    typed_fields: list[str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_api_fields(
            raw_fields,
            typed_fields,
            resolver=resolve,
            stdin=StringIO(""),
        )
