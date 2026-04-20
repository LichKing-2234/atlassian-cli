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


def collect_env_headers(env: dict[str, str]) -> dict[str, str]:
    value = env.get("ATLASSIAN_HEADER")
    if not value:
        return {}
    return parse_cli_headers([value])
