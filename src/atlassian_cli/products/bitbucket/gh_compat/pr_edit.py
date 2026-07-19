from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import TextIO

import click

from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.services.pr_edit import (
    PullRequestEdits,
    reviewer_logins,
)

PromptText = Callable[..., str]
EditText = Callable[[str], str | None]

EDIT_FIELDS = ("title", "body", "base", "reviewers")


def normalize_reviewer_values(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in value.split(","):
            login = item.strip()
            if login and login not in seen:
                seen.add(login)
                normalized.append(login)
    return tuple(normalized)


def read_body_file(value: str, *, stdin: TextIO) -> str:
    if value == "-":
        return stdin.read()
    return Path(value).read_text(encoding="utf-8")


def _selected_fields(value: str) -> tuple[str, ...]:
    selected = normalize_reviewer_values([value])
    if not selected:
        raise ValidationError("no pull request fields selected")
    invalid = [field for field in selected if field not in EDIT_FIELDS]
    if invalid:
        raise ValidationError(f"unknown pull request edit field: {invalid[0]}")
    return selected


def _current_base(current: Mapping) -> str:
    destination = current.get("toRef")
    if not isinstance(destination, Mapping):
        return ""
    display_id = destination.get("displayId")
    if isinstance(display_id, str):
        return display_id
    ref_id = destination.get("id")
    return ref_id.removeprefix("refs/heads/") if isinstance(ref_id, str) else ""


def prompt_for_edits(
    current: Mapping,
    *,
    prompt: PromptText,
    edit: EditText,
) -> PullRequestEdits:
    selected = _selected_fields(prompt("Fields to edit (title, body, base, reviewers)"))
    values: dict[str, object] = {}

    if "title" in selected:
        values["title"] = prompt(
            "Title",
            default=str(current.get("title") or ""),
            show_default=False,
        )
    if "body" in selected:
        body = edit(str(current.get("description") or ""))
        if body is None:
            raise click.Abort()
        values["body"] = body
    if "base" in selected:
        values["base"] = prompt(
            "Base branch",
            default=_current_base(current),
            show_default=False,
        )
    if "reviewers" in selected:
        existing = reviewer_logins(current)
        updated = normalize_reviewer_values(
            [
                prompt(
                    "Reviewers",
                    default=",".join(existing),
                    show_default=False,
                )
            ]
        )
        existing_set = set(existing)
        updated_set = set(updated)
        values["add_reviewers"] = tuple(login for login in updated if login not in existing_set)
        values["remove_reviewers"] = tuple(login for login in existing if login not in updated_set)

    return PullRequestEdits(**values)
