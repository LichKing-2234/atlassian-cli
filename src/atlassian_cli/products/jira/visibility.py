import json


def parse_visibility(value: str | None, *, option_name: str) -> dict[str, str] | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{option_name} must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{option_name} must be a JSON object")
    visibility_type = parsed.get("type")
    visibility_value = parsed.get("value")
    if visibility_type not in {"role", "group"}:
        raise ValueError(f"{option_name} type must be role or group")
    if not isinstance(visibility_value, str) or not visibility_value.strip():
        raise ValueError(f"{option_name} value must be a non-empty string")
    return {"type": visibility_type, "value": visibility_value}
