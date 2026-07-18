from copy import deepcopy
from io import StringIO

import click
import pytest

from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.gh_compat.pr_edit import (
    normalize_reviewer_values,
    prompt_for_edits,
    read_body_file,
)

RAW_PR = {
    "title": "Example pull request",
    "description": "example response",
    "toRef": {"id": "refs/heads/main", "displayId": "main"},
    "reviewers": [
        {"user": {"name": "reviewer-one"}},
        {"user": {"slug": "reviewer-two"}},
    ],
}


def test_normalize_reviewer_values_splits_repeated_and_comma_values() -> None:
    assert normalize_reviewer_values(
        ["reviewer-one,reviewer-two", "reviewer-one", " reviewer-three ", ","],
    ) == ("reviewer-one", "reviewer-two", "reviewer-three")


def test_read_body_file_reads_utf8_text(tmp_path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text("example response\n", encoding="utf-8")

    assert read_body_file(str(body_file), stdin=StringIO("unused")) == "example response\n"


def test_read_body_file_reads_stdin_once() -> None:
    class CountingStdin(StringIO):
        reads = 0

        def read(self, *args, **kwargs):
            self.reads += 1
            return super().read(*args, **kwargs)

    stdin = CountingStdin("example response\n")

    assert read_body_file("-", stdin=stdin) == "example response\n"
    assert stdin.reads == 1


def test_read_body_file_preserves_missing_file_error(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="missing.md"):
        read_body_file(str(tmp_path / "missing.md"), stdin=StringIO())


def test_prompt_for_edits_seeds_values_and_computes_reviewer_changes() -> None:
    answers = iter(
        [
            "title,base,reviewers",
            "",
            "develop",
            "reviewer-two,reviewer-three",
        ]
    )
    calls = []

    def prompt(label, **kwargs):
        calls.append((label, kwargs))
        return next(answers)

    edits = prompt_for_edits(
        deepcopy(RAW_PR),
        prompt=prompt,
        edit=lambda _value: pytest.fail("editor called"),
    )

    assert edits.title == ""
    assert edits.body is None
    assert edits.base == "develop"
    assert edits.add_reviewers == ("reviewer-three",)
    assert edits.remove_reviewers == ("reviewer-one",)
    assert calls[1] == ("Title", {"default": "Example pull request", "show_default": False})
    assert calls[2] == ("Base branch", {"default": "main", "show_default": False})
    assert calls[3] == (
        "Reviewers",
        {"default": "reviewer-one,reviewer-two", "show_default": False},
    )


def test_prompt_for_edits_uses_editor_for_body_and_preserves_empty_result() -> None:
    edited_values = []

    def editor(value: str) -> str:
        edited_values.append(value)
        return ""

    edits = prompt_for_edits(
        deepcopy(RAW_PR),
        prompt=lambda *_args, **_kwargs: "body",
        edit=editor,
    )

    assert edited_values == ["example response"]
    assert edits.body == ""


@pytest.mark.parametrize("selection", ["", "unknown", "title,unknown"])
def test_prompt_for_edits_rejects_empty_or_unknown_field_selection(selection: str) -> None:
    with pytest.raises(ValidationError):
        prompt_for_edits(
            deepcopy(RAW_PR),
            prompt=lambda *_args, **_kwargs: selection,
            edit=lambda value: value,
        )


def test_prompt_for_edits_treats_closed_editor_as_cancellation() -> None:
    with pytest.raises(click.Abort):
        prompt_for_edits(
            deepcopy(RAW_PR),
            prompt=lambda *_args, **_kwargs: "body",
            edit=lambda _value: None,
        )
