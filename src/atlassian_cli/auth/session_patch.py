def patch_session_headers(session, headers: dict[str, str]) -> None:
    if not headers:
        return

    original_request = session.request

    def request(method, url, **kwargs):
        request_headers = {**headers, **(kwargs.get("headers") or {})}
        kwargs["headers"] = request_headers
        return original_request(method, url, **kwargs)

    session.request = request
