from collections.abc import Mapping


def parse_cli_headers(values: list[str] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values or []:
        if ":" not in value:
            raise ValueError(f"Invalid header format: {value}")
        name, raw = value.split(":", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid header format: {value}")
        headers[name] = raw.lstrip()
    return headers


def merge_headers(*header_maps: Mapping[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    names: dict[str, str] = {}
    for headers in header_maps:
        for name, value in headers.items():
            normalized = name.lower()
            previous = names.get(normalized)
            if previous is not None:
                del merged[previous]
            merged[name] = value
            names[normalized] = name
    return merged
