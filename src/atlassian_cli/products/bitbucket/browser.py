from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import DiffLexer

from atlassian_cli.output.markdown import excerpt_text, render_markdown_preview


def _user_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("display_name") or value.get("name") or "")
    if isinstance(value, str):
        return value
    return ""


def _reviewer_summary(value: Any) -> str:
    if not isinstance(value, list):
        return ""

    names = [_user_name(item) for item in value if isinstance(item, Mapping)]
    names = [name for name in names if name]
    if len(names) <= 3:
        return ", ".join(names)
    return ", ".join([*names[:3], f"+{len(names) - 3} more"])


def _ref_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("display_id") or value.get("id") or "")
    return ""


def _format_updated(value: Any) -> str:
    if value in (None, ""):
        return ""

    text = str(value)
    if text.isdigit():
        timestamp = int(text)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text


def render_pull_request_item(index: int, item: dict[str, Any]) -> str:
    parts = [
        str(item.get("id", "")).strip(),
        str(item.get("state", "")).strip(),
        _user_name(item.get("author")),
        str(item.get("title", "")).strip(),
    ]
    return "  ".join(part for part in parts if part)


def render_pull_request_preview(item: dict[str, Any]) -> str:
    lines: list[str] = []
    for label, value in (
        ("State", item.get("state")),
        ("Author", _user_name(item.get("author"))),
        ("Reviewers", _reviewer_summary(item.get("reviewers"))),
        ("From", _ref_name(item.get("from_ref"))),
        ("To", _ref_name(item.get("to_ref"))),
        ("Updated", _format_updated(item.get("updated_date"))),
    ):
        if value:
            lines.append(f"{label}: {value}")

    description = excerpt_text(item.get("description"), max_lines=3)
    if description:
        lines.extend(["", "Description:", description])

    return "\n".join(lines) or render_markdown_preview(item)


def _render_diff(diff: str, *, colorize: bool) -> str:
    diff = diff.rstrip()
    if not colorize:
        return diff
    return highlight(diff, DiffLexer(), TerminalFormatter()).rstrip()


def render_pull_request_detail(item: dict[str, Any], *, colorize_diff: bool = False) -> str:
    identifier = str(item.get("id", "")).strip() or "Pull request"
    title = str(item.get("title", "")).strip()
    heading = f"# {identifier} - {title}" if title else f"# {identifier}"

    lines = [heading]
    for label, value in (
        ("State", item.get("state")),
        ("Author", _user_name(item.get("author"))),
        ("Reviewers", _reviewer_summary(item.get("reviewers"))),
        ("From", _ref_name(item.get("from_ref"))),
        ("To", _ref_name(item.get("to_ref"))),
        ("Created", _format_updated(item.get("created_date"))),
        ("Updated", _format_updated(item.get("updated_date"))),
    ):
        if value:
            lines.append(f"- {label}: {value}")

    description = item.get("description")
    if description:
        lines.extend(["", "## Description", str(description).strip()])

    diff = item.get("diff")
    if diff:
        lines.extend(["", "## Diff", _render_diff(str(diff), colorize=colorize_diff)])

    return "\n".join(lines).strip()
