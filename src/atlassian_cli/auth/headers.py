def _canonical_header_name(suffix: str) -> str:
    special_cases = {
        "AUTHORIZATION": "Authorization",
        "COOKIE": "Cookie",
    }
    if suffix in special_cases:
        return special_cases[suffix]
    return "-".join(part.capitalize() for part in suffix.split("_"))


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
    headers: dict[str, str] = {}
    prefix = "ATLASSIAN_HEADER_"
    for key, value in env.items():
        if key.startswith(prefix):
            headers[_canonical_header_name(key[len(prefix) :])] = value
    return headers
