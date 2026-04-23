from typing import Any


def coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def nested_get(data: dict[str, Any] | None, *path: str) -> Any:
    current: Any = data or {}
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def adf_to_text(node: Any) -> str:
    if isinstance(node, list):
        return "".join(adf_to_text(item) for item in node)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text", ""))
    return "".join(adf_to_text(child) for child in node.get("content", []))
