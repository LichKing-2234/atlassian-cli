from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from atlassian_cli.products.bitbucket.providers.base import BitbucketProvider


@dataclass(frozen=True)
class ApiRequest:
    endpoint: str
    method: str
    headers: dict[str, str]
    fields: dict[str, object]
    input_body: bytes | None = None


def normalize_api_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if parsed.scheme or parsed.netloc:
        raise ValueError("absolute API endpoints are not supported")
    if parsed.fragment:
        raise ValueError("API endpoints must not contain a fragment")

    path = parsed.path.removeprefix("/")
    if path == "graphql":
        raise ValueError("GraphQL is not supported")
    if not path.startswith("rest/"):
        path = f"rest/api/1.0/{path}"
    return urlunsplit(("", "", path, parsed.query, ""))


def _has_header(headers: dict[str, str], name: str) -> bool:
    expected = name.lower()
    return any(key.lower() == expected for key in headers)


def _is_json_response(response) -> bool:
    content_type = str(response.headers.get("Content-Type", ""))
    media_type = content_type.partition(";")[0].strip().lower()
    return media_type.endswith("/json") or media_type.endswith("+json")


def _query_values(path: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for key, value in parse_qsl(urlsplit(path).query, keep_blank_values=True):
        values.setdefault(key, []).append(value)
    return values


def _add_query_param(params: dict[str, object], key: str, value: object) -> None:
    if isinstance(value, dict):
        for subkey, item in value.items():
            _add_query_param(params, subkey, item)
        return
    if isinstance(value, list):
        for item in value:
            _add_query_param(params, f"{key}[]", item)
        return

    if isinstance(value, bool):
        encoded: object = str(value).lower()
    elif value is None:
        encoded = ""
    elif isinstance(value, (int, str)):
        encoded = value
    else:
        raise ValueError(f"unsupported API query parameter type: {type(value).__name__}")

    if key not in params:
        params[key] = encoded
        return
    existing = params[key]
    if isinstance(existing, list):
        existing.append(encoded)
    else:
        params[key] = [existing, encoded]


def _query_params(fields: dict[str, object]) -> dict[str, object]:
    params: dict[str, object] = {}
    for key, value in fields.items():
        _add_query_param(params, key, value)
    return params


def _replace_query_value(path: str, key: str, value: object) -> str:
    parsed = urlsplit(path)
    pairs = [
        (name, item)
        for name, item in parse_qsl(parsed.query, keep_blank_values=True)
        if name != key
    ]
    pairs.append((key, str(value)))
    return urlunsplit(("", "", parsed.path, urlencode(pairs), ""))


def _integer(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid Bitbucket pagination {label}: {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid Bitbucket pagination {label}: {value!r}") from exc


class BitbucketApiService:
    def __init__(self, provider: BitbucketProvider) -> None:
        self.provider = provider

    def iter_responses(
        self,
        request: ApiRequest,
        *,
        paginate: bool,
    ) -> Iterator[object]:
        method = request.method.upper()
        if paginate and method != "GET":
            raise ValueError("the --paginate option is not supported for non-GET requests")

        path = normalize_api_endpoint(request.endpoint)
        headers = dict(request.headers)
        if not _has_header(headers, "Accept"):
            headers["Accept"] = "*/*"

        fields = dict(request.fields)
        if request.input_body is not None:
            params = fields or None
            json_body = None
            data = request.input_body
        elif method == "GET":
            params = fields or None
            json_body = None
            data = None
        else:
            params = None
            json_body = fields or None
            data = None
            if json_body is not None and not _has_header(headers, "Content-Type"):
                headers["Content-Type"] = "application/json; charset=utf-8"

        query_values = _query_values(path)
        if paginate and "limit" not in query_values and (params is None or "limit" not in params):
            params = dict(params or {})
            params["limit"] = 100

        current_start = 0
        start_in_path = "start" in query_values
        if start_in_path:
            current_start = _integer(query_values["start"][-1], label="start")
        elif params is not None and "start" in params:
            current_start = _integer(params["start"], label="start")
        seen_starts = {current_start}

        while True:
            response = self.provider.request_api(
                method,
                path,
                headers=headers,
                params=_query_params(params) if params is not None else None,
                json_body=json_body,
                data=data,
            )
            yield response

            if not paginate or getattr(response, "status_code", 0) >= 300:
                return
            if not _is_json_response(response):
                return
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError("unable to decode paginated Bitbucket response as JSON") from exc
            if not isinstance(payload, dict) or "isLastPage" not in payload:
                return
            if payload["isLastPage"] is True:
                return
            if payload["isLastPage"] is not False or "nextPageStart" not in payload:
                raise ValueError("invalid Bitbucket pagination nextPageStart")

            next_start = _integer(payload["nextPageStart"], label="nextPageStart")
            if next_start <= current_start or next_start in seen_starts:
                raise ValueError(f"invalid Bitbucket pagination nextPageStart: {next_start!r}")
            seen_starts.add(next_start)
            current_start = next_start

            if start_in_path:
                path = _replace_query_value(path, "start", next_start)
            else:
                params = dict(params or {})
                params["start"] = next_start
            json_body = None
            data = None
