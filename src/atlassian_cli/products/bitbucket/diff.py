from __future__ import annotations

from collections.abc import Mapping
from typing import Any

COMMENTABLE_LINE_TYPES = {"ADDED", "REMOVED", "CONTEXT"}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _path_to_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        return ""

    for key in ("toString", "path", "displayId", "name"):
        item = value.get(key)
        if isinstance(item, str) and item:
            return item

    components = value.get("components")
    if isinstance(components, list):
        parts = [str(item) for item in components if str(item)]
        if parts:
            return "/".join(parts)

    parent = _path_to_string(value.get("parent"))
    name = value.get("name")
    if parent and isinstance(name, str) and name:
        return f"{parent}/{name}"
    if isinstance(name, str):
        return name
    return ""


def _file_path(file_data: Mapping[str, Any]) -> str:
    return (
        _path_to_string(file_data.get("destination"))
        or _path_to_string(file_data.get("source"))
        or _path_to_string(file_data.get("path"))
    )


def _line_number(data: Mapping[str, Any], *keys: str) -> int | None:
    value = _first_present(*(data.get(key) for key in keys))
    if value in (None, ""):
        return None
    return int(value)


def _line_text(data: Mapping[str, Any]) -> str:
    value = _first_present(data.get("line"), data.get("text"))
    return "" if value is None else str(value)


def _line_type(segment: Mapping[str, Any], line: Mapping[str, Any]) -> str:
    value = _first_present(line.get("type"), segment.get("type"), "")
    return str(value).upper()


def _anchor(path: str, line_type: str, old_line: int | None, new_line: int | None) -> dict | None:
    if line_type not in COMMENTABLE_LINE_TYPES:
        return None
    if line_type == "REMOVED":
        line = old_line
    else:
        line = new_line if new_line is not None else old_line
    if not path or line is None:
        return None
    return {"path": path, "line": line, "line_type": line_type}


def _normalize_line(
    *,
    path: str,
    segment: Mapping[str, Any],
    line: Mapping[str, Any],
) -> dict[str, Any]:
    line_type = _line_type(segment, line)
    old_line = _line_number(line, "source", "sourceLine", "oldLine", "old_line")
    new_line = _line_number(
        line,
        "destination",
        "destinationLine",
        "newLine",
        "new_line",
    )
    if line_type == "ADDED":
        old_line = None
    elif line_type == "REMOVED":
        new_line = None

    payload: dict[str, Any] = {
        "type": line_type,
        "old_line": old_line,
        "new_line": new_line,
        "text": _line_text(line),
    }
    anchor = _anchor(path, line_type, old_line, new_line)
    if anchor:
        payload["anchor"] = anchor
    return payload


def _normalize_hunk(path: str, hunk: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source_start": _line_number(hunk, "sourceLine", "source_start"),
        "source_span": _line_number(hunk, "sourceSpan", "source_span"),
        "destination_start": _line_number(hunk, "destinationLine", "destination_start"),
        "destination_span": _line_number(hunk, "destinationSpan", "destination_span"),
    }

    lines: list[dict[str, Any]] = []
    for segment in hunk.get("segments", []):
        if not isinstance(segment, Mapping):
            continue
        for line in segment.get("lines", []):
            if isinstance(line, Mapping):
                lines.append(_normalize_line(path=path, segment=segment, line=line))

    payload["lines"] = lines
    return {key: value for key, value in payload.items() if value not in (None, [], {})}


def normalize_pull_request_diff(pr_id: int, data: Mapping[str, Any]) -> dict[str, Any]:
    files = []
    raw_files = data.get("values")
    if raw_files is None:
        raw_files = data.get("diffs", [])

    for file_data in raw_files:
        if not isinstance(file_data, Mapping):
            continue
        path = _file_path(file_data)
        hunks = [
            _normalize_hunk(path, hunk)
            for hunk in file_data.get("hunks", [])
            if isinstance(hunk, Mapping)
        ]
        files.append({"path": path, "hunks": hunks})

    return {"id": pr_id, "files": files}
