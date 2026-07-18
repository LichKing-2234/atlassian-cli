from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime
from io import StringIO
from typing import Any

from rich.cells import cell_len
from rich.console import Console
from rich.markdown import Markdown

from atlassian_cli.compat import UTC
from atlassian_cli.core.errors import AtlassianCliError

MISSING_JSON_VALUE = "__ATLASSIAN_MISSING_JSON_VALUE__"

JSON_FIELDS = (
    "additions",
    "author",
    "baseRefName",
    "baseRefOid",
    "body",
    "changedFiles",
    "closed",
    "closedAt",
    "comments",
    "commits",
    "createdAt",
    "deletions",
    "files",
    "fullDatabaseId",
    "headRefName",
    "headRefOid",
    "headRepository",
    "headRepositoryOwner",
    "id",
    "isCrossRepository",
    "latestReviews",
    "mergeCommit",
    "mergedAt",
    "mergedBy",
    "mergeable",
    "mergeStateStatus",
    "number",
    "potentialMergeCommit",
    "reviewDecision",
    "reviewRequests",
    "reviews",
    "state",
    "statusCheckRollup",
    "title",
    "updatedAt",
    "url",
)

BLOCKED_FIELDS = {
    "latestReviews": ("B30", "atomic pull-request review records"),
    "reviews": ("B30", "atomic pull-request review records"),
    "mergeCommit": ("B31", "pull-request merge-commit identity"),
    "potentialMergeCommit": ("B25", "potential merge commit"),
}

COLOR_DELIM = "1;37"
COLOR_KEY = "1;34"
COLOR_NULL = "36"
COLOR_STRING = "32"
COLOR_BOOL = "33"


class GhPreflightError(AtlassianCliError):
    """A gh-compatible argument or capability error."""


def _available_fields(fields: Sequence[str]) -> str:
    return "\n".join(f"  {field}" for field in sorted(fields))


def _requested_fields(value: str | Sequence[str]) -> list[str]:
    values = [value] if isinstance(value, str) else value
    return [field.strip() for item in values for field in item.split(",")]


def validate_json_field_names(
    value: str | Sequence[str] | None,
    *,
    web: bool,
    available_fields: Sequence[str],
) -> tuple[str, ...] | None:
    if value is None or (not isinstance(value, str) and not value):
        return None

    requested = _requested_fields(value)
    available = _available_fields(available_fields)
    if MISSING_JSON_VALUE in requested:
        raise GhPreflightError(
            f"Specify one or more comma-separated fields for `--json`:\n{available}"
        )
    if web:
        raise GhPreflightError("cannot use `--web` with `--json`")

    unknown = next((field for field in requested if field not in available_fields), None)
    if unknown is not None:
        raise GhPreflightError(f'Unknown JSON field: "{unknown}"\nAvailable fields:\n{available}')

    return tuple(dict.fromkeys(requested))


def validate_json_fields(
    value: str | Sequence[str] | None,
    *,
    web: bool,
    surface: str,
) -> tuple[str, ...] | None:
    deduplicated = validate_json_field_names(
        value,
        web=web,
        available_fields=JSON_FIELDS,
    )
    if deduplicated is None:
        return None

    for field in deduplicated:
        blocker = BLOCKED_FIELDS.get(field)
        if blocker is None:
            continue
        code, capability = blocker
        raise GhPreflightError(
            f"unsupported by Bitbucket Server 6.7.2: {capability} ({code}); "
            f"required by gh v2.96.0 {surface} --json {field}"
        )
    return deduplicated


def _colored(code: str, value: str) -> str:
    return f"\x1b[{code}m{value}\x1b[m"


def _json_atom(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _render_color_json(value: Any, depth: int = 0) -> str:
    indent = "  " * depth
    child_indent = "  " * (depth + 1)
    if isinstance(value, dict):
        if not value:
            return f"{_colored(COLOR_DELIM, '{')}{_colored(COLOR_DELIM, '}')}"
        items = []
        for key in sorted(value):
            rendered_key = _colored(COLOR_KEY, _json_atom(str(key)))
            separator = _colored(COLOR_DELIM, ":")
            items.append(
                f"{child_indent}{rendered_key}{separator} "
                f"{_render_color_json(value[key], depth + 1)}"
            )
        delimiter = _colored(COLOR_DELIM, ",")
        joined_items = f"{delimiter}\n".join(items)
        return f"{_colored(COLOR_DELIM, '{')}\n{joined_items}\n{indent}{_colored(COLOR_DELIM, '}')}"
    if isinstance(value, list):
        if not value:
            return f"{_colored(COLOR_DELIM, '[')}{_colored(COLOR_DELIM, ']')}"
        items = [f"{child_indent}{_render_color_json(item, depth + 1)}" for item in value]
        delimiter = _colored(COLOR_DELIM, ",")
        joined_items = f"{delimiter}\n".join(items)
        return f"{_colored(COLOR_DELIM, '[')}\n{joined_items}\n{indent}{_colored(COLOR_DELIM, ']')}"
    if value is None:
        return _colored(COLOR_NULL, "null")
    if isinstance(value, bool):
        return _colored(COLOR_BOOL, _json_atom(value))
    if isinstance(value, str):
        return _colored(COLOR_STRING, _json_atom(value))
    return _json_atom(value)


def render_json(value: Any, *, color: bool) -> str:
    if color:
        return f"{_render_color_json(value)}\n"
    return f"{_json_atom(value)}\n"


def _style(value: str, code: str, *, color: bool) -> str:
    return f"\x1b[{code}m{value}\x1b[0m" if color else value


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _fuzzy_ago(now: datetime, value: object) -> str:
    instant = _parse_time(value)
    if instant is None:
        return ""
    seconds = max(0, int((now - instant).total_seconds()))
    if seconds < 60:
        return "less than a minute ago"
    if seconds < 60 * 60:
        minutes = seconds // 60
        return f"about {minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 24 * 60 * 60:
        hours = seconds // (60 * 60)
        return f"about {hours} hour{'s' if hours != 1 else ''} ago"
    if seconds < 30 * 24 * 60 * 60:
        days = seconds // (24 * 60 * 60)
        return f"about {days} day{'s' if days != 1 else ''} ago"
    if seconds < 365 * 24 * 60 * 60:
        months = seconds // (24 * 60 * 60) // 30
        return f"about {months} month{'s' if months != 1 else ''} ago"
    years = seconds // (24 * 60 * 60) // 365
    return f"about {years} year{'s' if years != 1 else ''} ago"


def _fuzzy_ago_abbr(now: datetime, value: object) -> str:
    instant = _parse_time(value)
    if instant is None:
        return ""
    seconds = max(0, int((now - instant).total_seconds()))
    if seconds < 60 * 60:
        return f"{seconds // 60}m"
    if seconds < 24 * 60 * 60:
        return f"{seconds // (60 * 60)}h"
    if seconds < 30 * 24 * 60 * 60:
        return f"{seconds // (24 * 60 * 60)}d"
    return f"{instant:%b} {instant.day:2d}, {instant.year}"


def _collapse_whitespace(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _state_color(state: object) -> str:
    return {"OPEN": "32", "DECLINED": "31", "MERGED": "35"}.get(str(state), "")


def _truncate_display(value: str, width: int) -> str:
    if cell_len(value) <= width:
        return value
    if width <= 0:
        return ""
    if width == 1:
        return "…"
    prefix = ""
    for character in value:
        candidate = f"{prefix}{character}"
        if cell_len(candidate) > width - 1:
            break
        prefix = candidate
    return f"{prefix}…"


def _format_tty_table(
    rows: list[list[str]],
    colors: list[list[str | None]],
    *,
    max_width: int | None = None,
) -> str:
    widths = [max(cell_len(row[index]) for row in rows) for index in range(len(rows[0]))]
    spacing = 2
    if max_width is not None:
        content_budget = max_width - spacing * (len(widths) - 1)
        while sum(widths) > content_budget and any(width > 1 for width in widths):
            widest = max(
                (index for index, width in enumerate(widths) if width > 1),
                key=lambda index: widths[index],
            )
            widths[widest] -= 1
    rendered_rows: list[str] = []
    for row_index, row in enumerate(rows):
        cells: list[str] = []
        for index, value in enumerate(row):
            value = _truncate_display(value, widths[index])
            code = colors[row_index][index]
            content = _style(value, code, color=code is not None) if code else value
            if index < len(row) - 1:
                content += " " * (widths[index] - cell_len(value) + spacing)
            cells.append(content)
        rendered_rows.append("".join(cells))
    return "\n".join(rendered_rows)


def render_pr_list(
    pull_requests: Sequence[dict],
    *,
    repository: str,
    total: int | None,
    filtered: bool,
    tty: bool,
    color: bool,
    now: datetime,
    width: int | None = None,
) -> str:
    if not pull_requests:
        return ""

    if not tty:
        lines = []
        for pull_request in pull_requests:
            lines.append(
                "\t".join(
                    (
                        str(pull_request.get("number", "")),
                        _collapse_whitespace(pull_request.get("title")),
                        str(pull_request.get("headRefName") or ""),
                        str(pull_request.get("state") or ""),
                        str(pull_request.get("createdAt") or ""),
                    )
                )
            )
        return "\n".join(lines) + "\n"

    shown = len(pull_requests)
    total = shown if total is None else total
    if filtered:
        noun = "pull request" if total == 1 else "pull requests"
        match = "matches" if total == 1 else "match"
        header = f"Showing {shown} of {total} {noun} in {repository} that {match} your search"
    else:
        noun = "open pull request" if total == 1 else "open pull requests"
        header = f"Showing {shown} of {total} {noun} in {repository}"

    table_rows = [["ID", "TITLE", "BRANCH", "CREATED AT"]]
    table_colors: list[list[str | None]] = [
        ["1" if color else None] * 4,
    ]
    for pull_request in pull_requests:
        state_code = _state_color(pull_request.get("state")) if color else ""
        table_rows.append(
            [
                f"#{pull_request.get('number', '')}",
                _collapse_whitespace(pull_request.get("title")),
                str(pull_request.get("headRefName") or ""),
                _fuzzy_ago(now, pull_request.get("createdAt")),
            ]
        )
        table_colors.append(
            [
                state_code or None,
                None,
                "36" if color else None,
                "2" if color else None,
            ]
        )
    table = _format_tty_table(table_rows, table_colors, max_width=width)
    return f"\n{header}\n\n{table}\n"


def _user_name(value: object, *, display: bool = False) -> str:
    if not isinstance(value, dict):
        return ""
    if display:
        return str(value.get("name") or value.get("login") or "")
    return str(value.get("login") or value.get("name") or "")


def _reviewer_state(value: object) -> str:
    state = str(value or "").upper()
    if state == "APPROVED":
        return "Approved"
    if state in {"NEEDS_WORK", "CHANGES_REQUESTED"}:
        return "Changes requested"
    return "Requested"


def _reviewer_list(pull_request: dict, *, color: bool) -> str:
    reviewers: list[tuple[bool, str, str]] = []
    for reviewer_projection in pull_request.get("_reviewers") or []:
        if not isinstance(reviewer_projection, dict):
            continue
        reviewer = reviewer_projection.get("user")
        name = _user_name(reviewer)
        if not name:
            continue
        display = _reviewer_state(reviewer_projection.get("status"))
        reviewers.append((display == "Requested", name, display))
    reviewers.sort(key=lambda item: (item[0], item[1]))

    formatted = []
    for _, name, display in reviewers:
        code = {
            "Approved": "32",
            "Changes requested": "31",
            "Requested": "33",
        }[display]
        formatted.append(f"{name} ({_style(display, code, color=color)})")
    return ", ".join(formatted)


def _check_summary(pull_request: dict, *, color: bool) -> str:
    checks = [
        item for item in pull_request.get("statusCheckRollup") or [] if isinstance(item, dict)
    ]
    if not checks:
        return _style("No checks", "2", color=color)
    states = [str(item.get("state") or "").upper() for item in checks]
    failing = sum(state in {"ERROR", "FAILURE"} for state in states)
    pending = sum(state in {"EXPECTED", "PENDING", "QUEUED", "IN_PROGRESS"} for state in states)
    if failing:
        message = (
            "× All checks failing"
            if failing == len(states)
            else f"× {failing}/{len(states)} checks failing"
        )
        return _style(message, "31", color=color)
    if pending:
        return _style("- Checks pending", "33", color=color)
    if states and all(state in {"SUCCESS", "NEUTRAL", "SKIPPED"} for state in states):
        return _style("✓ Checks passing", "32", color=color)
    return _style("No checks", "2", color=color)


def _render_markdown(value: object, *, width: int, color: bool) -> str:
    text = str(value or "")
    if not text:
        message = _style("No description provided", "2", color=color)
        return f"\n  {message}\n"
    output = StringIO()
    console = Console(
        file=output,
        width=width,
        height=25,
        force_terminal=color,
        color_system="standard" if color else None,
        no_color=not color,
        legacy_windows=False,
    )
    console.print(Markdown(text))
    return "\n".join(line.rstrip() for line in output.getvalue().splitlines()).rstrip()


def _sorted_comments(pull_request: dict) -> list[dict]:
    comments = [item for item in pull_request.get("comments") or [] if isinstance(item, dict)]
    return sorted(comments, key=lambda item: str(item.get("createdAt") or ""))


def _raw_comments(pull_request: dict) -> str:
    blocks = []
    for comment in _sorted_comments(pull_request):
        association = str(comment.get("authorAssociation") or "NONE").lower()
        edited = comment.get("createdAt") != comment.get("updatedAt")
        status = str(comment.get("status") or "none").lower().replace("_", " ")
        blocks.append(
            f"author:\t{_user_name(comment.get('author'))}\n"
            f"association:\t{association}\n"
            f"edited:\t{str(edited).lower()}\n"
            f"status:\t{status}\n"
            "--\n"
            f"{comment.get('body') or ''}\n"
            "--\n"
        )
    return "".join(blocks)


def _tty_comments(
    pull_request: dict,
    *,
    show_all: bool,
    now: datetime,
    width: int,
    color: bool,
) -> str:
    all_comments = _sorted_comments(pull_request)
    comments = all_comments if show_all else all_comments[-1:]
    rendered = ""
    if not show_all and len(all_comments) > 1:
        hidden = len(all_comments) - 1
        noun = "comment" if hidden == 1 else "comments"
        notice = f"———————— Not showing {hidden} {noun} ————————"
        rendered += f"{_style(notice, '2', color=color)}\n\n\n"

    for index, comment in enumerate(comments):
        newest = index == len(comments) - 1
        author = _style(_user_name(comment.get("author")), "1", color=color)
        relative = _fuzzy_ago_abbr(now, comment.get("createdAt"))
        header = f"{author}{_style(f' • {relative}', '1', color=color)}"
        if comment.get("createdAt") != comment.get("updatedAt"):
            header += _style(" • Edited", "1", color=color)
        if newest:
            header += _style(" • ", "1", color=color)
            header += _style("Newest comment", "1;36", color=color)
        if comment.get("body"):
            body = f"{_render_markdown(comment['body'], width=width, color=color)}\n"
        else:
            message = _style("No body provided", "2", color=color)
            body = f"\n  {message}\n\n"
        footer = ""
        if comment.get("url"):
            footer = _style(f"View the full review: {comment['url']}\n\n", "2", color=color)
        rendered += f"{header}\n{body}{footer}"
        if newest:
            rendered += "\n"

    if not show_all and len(all_comments) > 1:
        suffix = _style("Use --comments to view the full conversation", "2", color=color)
        rendered += f"{suffix}\n"
    return rendered


def render_pr_view(
    pull_request: dict,
    *,
    repository: str,
    tty: bool,
    color: bool,
    comments: bool,
    now: datetime,
    width: int = 80,
) -> str:
    if not tty:
        if comments:
            return _raw_comments(pull_request)
        reviewers = _reviewer_list(pull_request, color=False)
        return (
            f"title:\t{pull_request.get('title') or ''}\n"
            f"state:\t{pull_request.get('state') or ''}\n"
            f"author:\t{_user_name(pull_request.get('author'), display=True)}\n"
            "labels:\t\n"
            "assignees:\t\n"
            f"reviewers:\t{reviewers}\n"
            "projects:\t\n"
            "milestone:\t\n"
            f"number:\t{pull_request.get('number', '')}\n"
            f"url:\t{pull_request.get('url') or ''}\n"
            f"additions:\t{pull_request.get('additions', 0)}\n"
            f"deletions:\t{pull_request.get('deletions', 0)}\n"
            "auto-merge:\tdisabled\n"
            "--\n"
            f"{pull_request.get('body') or ''}\n"
        )

    title = _style(str(pull_request.get("title") or ""), "1", color=color)
    state = str(pull_request.get("state") or "").title()
    state_code = _state_color(pull_request.get("state"))
    state = _style(state, state_code, color=color and bool(state_code))
    author = _user_name(pull_request.get("author"), display=True)
    commit_count = len(pull_request.get("commits") or [])
    commit_noun = "commit" if commit_count == 1 else "commits"
    created = _fuzzy_ago(now, pull_request.get("createdAt"))
    additions = _style(f"+{pull_request.get('additions', 0)}", "32", color=color)
    deletions = _style(f"-{pull_request.get('deletions', 0)}", "31", color=color)
    reviewers = _reviewer_list(pull_request, color=color)

    lines = [
        f"{title} {repository}#{pull_request.get('number', '')}",
        (
            f"{state} • {author} wants to merge {commit_count} {commit_noun} into "
            f"{pull_request.get('baseRefName') or ''} from "
            f"{pull_request.get('headRefName') or ''} • {created}"
        ),
        f"{additions} {deletions} • {_check_summary(pull_request, color=color)}",
    ]
    if reviewers:
        lines.append(f"{_style('Reviewers:', '1', color=color)} {reviewers}")

    body = _render_markdown(pull_request.get("body"), width=width, color=color)
    joined_lines = "\n".join(lines)
    rendered = f"{joined_lines}\n\n{body}\n\n"
    rendered_comments = _tty_comments(
        pull_request,
        show_all=comments,
        now=now,
        width=width,
        color=color,
    )
    if rendered_comments:
        rendered += rendered_comments
    footer = f"View this pull request in Bitbucket: {pull_request.get('url') or ''}"
    return f"{rendered}{_style(footer, '2', color=color)}\n"
