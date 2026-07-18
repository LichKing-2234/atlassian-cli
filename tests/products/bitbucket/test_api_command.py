from __future__ import annotations

import json
import re
from collections.abc import Sequence
from types import SimpleNamespace

import pytest
from requests import Request, Response
from typer.testing import CliRunner

from atlassian_cli.cli import app
from atlassian_cli.products.bitbucket.commands import api as api_module

runner = CliRunner()

BASE_ARGS = [
    "--url",
    "https://bitbucket.example.com",
    "--auth",
    "pat",
    "--token",
    "example-user-id",
    "bitbucket",
    "api",
]
COMPARE_CHANGES = "projects/DEMO/repos/example-repo/compare/changes"


def test_gh_api_command_normalizes_python310_required_metavar() -> None:
    assert api_module.GhApiCommand._normalize_usage_piece("{<endpoint>}") == "<endpoint>"
    assert api_module.GhApiCommand._normalize_usage_piece("[OPTIONS]") == "[OPTIONS]"


def make_response(
    payload: object | str | None,
    *,
    status: int = 200,
    reason: str = "OK",
    headers: dict[str, str] | None = None,
) -> Response:
    response = Response()
    response.status_code = status
    response.reason = reason
    if isinstance(payload, str):
        response._content = payload.encode()
        response.headers["Content-Type"] = "text/plain"
    elif payload is None:
        response._content = b""
    else:
        response._content = json.dumps(payload, separators=(",", ":")).encode()
        response.headers["Content-Type"] = "application/json"
    response.headers.update(headers or {})
    response.encoding = "utf-8"
    response.raw = SimpleNamespace(version=11)
    return response


class FakeProvider:
    def __init__(
        self,
        responses: Sequence[Response],
        *,
        request_headers: dict[str, str] | None = None,
        error: Exception | None = None,
        error_after: int | None = None,
    ) -> None:
        self.responses = iter(responses)
        self.request_headers = request_headers or {}
        self.error = error
        self.error_after = error_after
        self.calls: list[dict] = []

    def request_api(
        self,
        method,
        path,
        *,
        headers,
        params,
        json_body,
        data,
    ):
        call = {
            "method": method,
            "path": path,
            "headers": headers,
            "params": params,
            "json_body": json_body,
            "data": data,
        }
        self.calls.append(call)
        if self.error is not None and (
            self.error_after is None or len(self.calls) > self.error_after
        ):
            raise self.error

        response = next(self.responses)
        request_headers = {**headers, **self.request_headers}
        request = Request(
            method,
            f"https://bitbucket.example.com/{path}",
            headers=request_headers,
            params=params,
            json=json_body,
            data=data,
        ).prepare()
        response.request = request
        response.url = request.url
        return response


def invoke_api(
    monkeypatch,
    args: list[str],
    responses: Sequence[Response],
    *,
    input: str | None = None,
    request_headers: dict[str, str] | None = None,
    error: Exception | None = None,
    error_after: int | None = None,
    env: dict[str, str] | None = None,
):
    provider = FakeProvider(
        responses,
        request_headers=request_headers,
        error=error,
        error_after=error_after,
    )
    monkeypatch.setattr(api_module, "build_provider", lambda _context: provider)
    result = runner.invoke(
        app,
        [*BASE_ARGS, *args],
        input=input,
        env={
            "ATLASSIAN_DISABLE_UPDATE_CHECK": "1",
            "PAGER": "cat",
            **(env or {}),
        },
    )
    return result, provider


def test_bitbucket_api_default_get_outputs_raw_json(monkeypatch) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES],
        [make_response({"values": []})],
    )

    assert result.exit_code == 0
    assert result.stdout == '{"values":[]}'
    assert provider.calls[0]["method"] == "GET"
    assert provider.calls[0]["params"] is None


def test_bitbucket_api_outputs_raw_text(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        ["projects/DEMO/repos/example-repo/compare/diff"],
        [make_response("example response")],
    )

    assert result.exit_code == 0
    assert result.stdout == "example response"


def test_bitbucket_api_preserves_binary_response_bytes(monkeypatch) -> None:
    response = make_response(None, headers={"Content-Type": "application/octet-stream"})
    response._content = b"\xff\x00DEMO"

    result, _provider = invoke_api(monkeypatch, [COMPARE_CHANGES], [response])

    assert result.exit_code == 0
    assert result.stdout_bytes == b"\xff\x00DEMO"


def test_bitbucket_api_fields_derive_post_with_json_body(monkeypatch) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "-f", "title=Example pull request"],
        [make_response({"status": "DEMO"})],
    )

    assert result.exit_code == 0
    assert provider.calls[0]["method"] == "POST"
    assert provider.calls[0]["params"] is None
    assert provider.calls[0]["json_body"] == {"title": "Example pull request"}


def test_bitbucket_api_explicit_get_sends_fields_as_query(monkeypatch) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [
            "-X",
            "GET",
            COMPARE_CHANGES,
            "-f",
            "from=feature/DEMO-1234/example-change",
            "-f",
            "to=DEMO",
        ],
        [make_response({"values": []})],
    )

    assert result.exit_code == 0
    assert provider.calls[0]["method"] == "GET"
    assert provider.calls[0]["params"] == {
        "from": "feature/DEMO-1234/example-change",
        "to": "DEMO",
    }


def test_bitbucket_api_input_is_raw_body_and_fields_are_query(monkeypatch, tmp_path) -> None:
    input_file = tmp_path / "input.json"
    input_file.write_text('{"status":"DEMO"}', encoding="utf-8")

    result, provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--input", str(input_file), "-f", "value=DEMO"],
        [make_response({"status": "DEMO"})],
    )

    assert result.exit_code == 0
    assert provider.calls[0]["method"] == "POST"
    assert provider.calls[0]["params"] == {"value": "DEMO"}
    assert provider.calls[0]["json_body"] is None
    assert provider.calls[0]["data"] == b'{"status":"DEMO"}'


def test_bitbucket_api_input_dash_reads_stdin(monkeypatch) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--input", "-"],
        [make_response({"status": "DEMO"})],
        input="example response",
    )

    assert result.exit_code == 0
    assert provider.calls[0]["data"] == b"example response"


def test_bitbucket_api_command_headers_override_case_insensitively(monkeypatch) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [
            COMPARE_CHANGES,
            "-H",
            "Accept: text/plain",
            "-H",
            "accept: application/json",
        ],
        [make_response({"values": []})],
    )

    assert result.exit_code == 0
    assert provider.calls[0]["headers"] == {"accept": "application/json"}


def test_bitbucket_api_expands_repository_and_branch_placeholders(monkeypatch) -> None:
    monkeypatch.setattr(
        api_module,
        "resolve_repository",
        lambda _server: SimpleNamespace(
            repository=SimpleNamespace(project_key="DEMO", repo_slug="example-repo"),
            current_branch="feature/DEMO-1234/example-change",
        ),
    )
    monkeypatch.setattr(
        api_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: pytest.fail("Git snapshot should be reused"),
        raising=False,
    )
    result, provider = invoke_api(
        monkeypatch,
        [
            "-X",
            "GET",
            "projects/{project}/repos/{repo}/compare/changes",
            "-F",
            "from={branch}",
            "-F",
            "to=DEMO",
        ],
        [make_response({"values": []})],
    )

    assert result.exit_code == 0
    assert provider.calls[0]["path"] == (
        "rest/api/1.0/projects/DEMO/repos/example-repo/compare/changes"
    )
    assert provider.calls[0]["params"] == {
        "from": "feature/DEMO-1234/example-change",
        "to": "DEMO",
    }


def test_bitbucket_api_reuses_branch_snapshot_when_repository_placeholder_follows(
    monkeypatch,
) -> None:
    snapshot = SimpleNamespace(current_branch="feature/DEMO-1234/example-change")
    reads = []
    resolution_snapshots = []

    def resolve_repository(_server, *, snapshot=None):
        resolution_snapshots.append(snapshot)
        return SimpleNamespace(
            repository=SimpleNamespace(project_key="DEMO", repo_slug="example-repo"),
            current_branch=snapshot.current_branch,
        )

    monkeypatch.setattr(api_module, "resolve_repository", resolve_repository)
    monkeypatch.setattr(
        api_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: SimpleNamespace(read=lambda: reads.append(snapshot) or snapshot),
    )

    result, provider = invoke_api(
        monkeypatch,
        [
            "-X",
            "GET",
            "rest/api/1.0/branches/{branch}",
            "-F",
            "project={project}",
        ],
        [make_response({"status": "DEMO"})],
    )

    assert result.exit_code == 0
    assert reads == [snapshot]
    assert resolution_snapshots == [snapshot]
    assert provider.calls[0]["params"] == {"project": "DEMO"}


def test_bitbucket_api_branch_placeholder_does_not_require_repository_resolution(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api_module,
        "resolve_repository",
        lambda _server: pytest.fail("repository should not be resolved"),
    )
    monkeypatch.setattr(
        api_module,
        "GitRepositoryContext",
        lambda *_args, **_kwargs: SimpleNamespace(
            read=lambda: SimpleNamespace(current_branch="feature/DEMO-1234/example-change")
        ),
        raising=False,
    )

    result, provider = invoke_api(
        monkeypatch,
        ["rest/api/1.0/branches/{branch}"],
        [make_response({"status": "DEMO"})],
    )

    assert result.exit_code == 0
    assert provider.calls[0]["path"] == ("rest/api/1.0/branches/feature/DEMO-1234/example-change")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--paginate", "-X", "POST", COMPARE_CHANGES], "non-GET"),
        (["--slurp", COMPARE_CHANGES], "`--paginate` required"),
        (["--paginate", "--slurp", "--jq", ".", COMPARE_CHANGES], "not supported"),
        (["--jq", ".", "--silent", COMPARE_CHANGES], "only one"),
        (["--jq", ".", "--verbose", COMPARE_CHANGES], "only one"),
        (["--silent", "--verbose", COMPARE_CHANGES], "only one"),
    ],
)
def test_bitbucket_api_rejects_incompatible_flags_before_provider(
    monkeypatch,
    args: list[str],
    message: str,
) -> None:
    monkeypatch.setattr(
        api_module,
        "build_provider",
        lambda _context: pytest.fail("provider should not be built"),
    )

    result = runner.invoke(app, [*BASE_ARGS, *args])

    assert result.exit_code == 1
    assert message in result.stderr


def test_bitbucket_api_rejects_paginate_with_input_before_provider(monkeypatch, tmp_path) -> None:
    input_file = tmp_path / "input.json"
    input_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        api_module,
        "build_provider",
        lambda _context: pytest.fail("provider should not be built"),
    )

    result = runner.invoke(
        app,
        [*BASE_ARGS, "--paginate", "--input", str(input_file), COMPARE_CHANGES],
    )

    assert result.exit_code == 1
    assert "not supported with `--input`" in result.stderr


def test_bitbucket_api_rejects_malformed_fields_before_authentication(monkeypatch) -> None:
    monkeypatch.setattr(
        api_module,
        "build_provider",
        lambda _context: pytest.fail("provider should not be built"),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "bitbucket",
            "api",
            COMPARE_CHANGES,
            "-f",
            "value[]junk=example response",
        ],
    )

    assert result.exit_code == 1
    assert "invalid key" in result.stderr
    assert "authentication required" not in result.stderr


def test_bitbucket_api_static_field_validation_does_not_load_or_create_config(
    monkeypatch,
    tmp_path,
) -> None:
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr(
        api_module,
        "build_provider",
        lambda _context: pytest.fail("provider should not be built"),
    )

    result = runner.invoke(
        app,
        [
            "--config-file",
            str(config_file),
            "bitbucket",
            "api",
            COMPARE_CHANGES,
            "-F",
            "value[name]junk=example response",
        ],
    )

    assert result.exit_code == 1
    assert "invalid key" in result.stderr
    assert not config_file.exists()


@pytest.mark.parametrize(
    ("endpoint", "message"),
    [
        ("graphql", "GraphQL is not supported"),
        (
            "https://bitbucket.example.com/rest/api/1.0/projects/DEMO",
            "absolute API endpoints are not supported",
        ),
    ],
)
def test_bitbucket_api_rejects_unsupported_endpoint_before_provider(
    monkeypatch,
    endpoint: str,
    message: str,
) -> None:
    monkeypatch.setattr(
        api_module,
        "build_provider",
        lambda _context: pytest.fail("provider should not be built"),
    )

    result = runner.invoke(app, [*BASE_ARGS, endpoint])

    assert result.exit_code == 1
    assert message in result.stderr


def test_bitbucket_api_missing_authentication_exits_four(monkeypatch) -> None:
    monkeypatch.setattr(
        api_module,
        "build_provider",
        lambda _context: pytest.fail("provider should not be built"),
    )

    result = runner.invoke(
        app,
        [
            "--url",
            "https://bitbucket.example.com",
            "--auth",
            "basic",
            "bitbucket",
            "api",
            COMPARE_CHANGES,
        ],
    )

    assert result.exit_code == 4
    assert "authentication required" in result.stderr


def test_bitbucket_api_jq_outputs_each_selected_value(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--jq", ".values[].id"],
        [make_response({"values": [{"id": "DEMO-1"}, {"id": "DEMO-1234"}]})],
    )

    assert result.exit_code == 0
    assert result.stdout == "DEMO-1\nDEMO-1234\n"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("{id:.values[0].id}", '{"id":"DEMO-1"}\n'),
        ('.values[0].id == "DEMO-1"', "true\n"),
        (".missing", "\n"),
    ],
)
def test_bitbucket_api_jq_formats_non_string_results(
    monkeypatch,
    expression: str,
    expected: str,
) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--jq", expression],
        [make_response({"values": [{"id": "DEMO-1"}]})],
    )

    assert result.exit_code == 0
    assert result.stdout == expected


def test_bitbucket_api_paginate_runs_jq_per_page(monkeypatch) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--paginate", "--jq", ".values[].id"],
        [
            make_response(
                {
                    "isLastPage": False,
                    "nextPageStart": 100,
                    "values": [{"id": "DEMO-1"}],
                }
            ),
            make_response({"isLastPage": True, "values": [{"id": "DEMO-1234"}]}),
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == "DEMO-1\nDEMO-1234\n"
    assert len(provider.calls) == 2


def test_bitbucket_api_paginate_preserves_completed_pages_on_later_failure(monkeypatch) -> None:
    page = {"isLastPage": False, "nextPageStart": 100, "values": [{"id": "DEMO-1"}]}
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--paginate"],
        [make_response(page)],
        error=OSError("example response"),
        error_after=1,
    )

    assert result.exit_code == 1
    assert result.stdout == json.dumps(page, separators=(",", ":"))
    assert "example response" in result.stderr


def test_bitbucket_api_slurp_wraps_paginated_pages(monkeypatch) -> None:
    pages = [
        {"isLastPage": False, "nextPageStart": 100, "values": [{"id": "DEMO-1"}]},
        {"isLastPage": True, "values": [{"id": "DEMO-1234"}]},
    ]
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--paginate", "--slurp"],
        [make_response(page) for page in pages],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == pages


def test_bitbucket_api_silent_slurp_outputs_nothing(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--paginate", "--slurp", "--silent"],
        [make_response({"isLastPage": True, "values": []})],
    )

    assert result.exit_code == 0
    assert result.stdout == ""


def test_bitbucket_api_include_outputs_status_sorted_headers_and_body(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--include"],
        [
            make_response(
                {"values": []},
                headers={"X-Zeta": "DEMO-1234", "A-Example": "DEMO-1"},
            )
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("HTTP/1.1 200 OK\n")
    assert result.stdout.index("A-Example: DEMO-1") < result.stdout.index("X-Zeta: DEMO-1234")
    assert result.stdout.endswith('{"values":[]}')


def test_bitbucket_api_silent_suppresses_success_body(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--silent"],
        [make_response({"values": []})],
    )

    assert result.exit_code == 0
    assert result.stdout == ""


def test_bitbucket_api_silent_with_include_preserves_headers(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--silent", "--include"],
        [make_response({"values": []})],
    )

    assert result.exit_code == 0
    assert result.stdout.startswith("HTTP/1.1 200 OK\n")
    assert '{"values":[]}' not in result.stdout


def test_bitbucket_api_no_content_outputs_nothing(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES],
        [make_response(None, status=204, reason="No Content")],
    )

    assert result.exit_code == 0
    assert result.stdout == ""


def test_bitbucket_api_tty_colors_json_and_uses_pager(monkeypatch) -> None:
    captured = {}
    monkeypatch.delenv("NO_COLOR", raising=False)

    def capture_stream(chunks, **kwargs) -> None:
        captured["text"] = b"".join(chunks)
        captured["kwargs"] = kwargs

    monkeypatch.setattr(api_module, "stream_output", capture_stream)
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES],
        [make_response({"values": []})],
        env={"ATLASSIAN_FORCE_TTY": "1"},
    )

    assert result.exit_code == 0
    assert b"\x1b[" in captured["text"]
    assert captured["kwargs"]["tty"] is True


def test_bitbucket_api_tty_formats_structured_jq_output(monkeypatch) -> None:
    captured = {}
    monkeypatch.delenv("NO_COLOR", raising=False)

    def capture_stream(chunks, **_kwargs) -> None:
        captured["text"] = b"".join(chunks)

    monkeypatch.setattr(api_module, "stream_output", capture_stream)
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--jq", "{id:.values[0].id}"],
        [make_response({"values": [{"id": "DEMO-1"}]})],
        env={"ATLASSIAN_FORCE_TTY": "1"},
    )

    assert result.exit_code == 0
    assert b"\x1b[" in captured["text"]
    plain = re.sub(rb"\x1b\[[0-9;]*m", b"", captured["text"])
    assert b'  "id"' in plain


def test_bitbucket_api_invalid_jq_exits_one(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--jq", ".["],
        [make_response({"values": []})],
    )

    assert result.exit_code == 1
    assert result.stderr.startswith("Error:")


def test_bitbucket_api_verbose_redacts_credentials_and_configured_headers(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--verbose"],
        [make_response({"status": "DEMO"})],
        request_headers={
            "Authorization": "Bearer example response",
            "accessToken": "example response",
            "Cookie": "example response",
        },
    )

    assert result.exit_code == 0
    assert "example response" not in result.stdout
    assert "> Authorization: REDACTED" in result.stdout
    assert "> accessToken: REDACTED" in result.stdout
    assert "> Cookie: REDACTED" in result.stdout
    assert "< HTTP/1.1 200 OK" in result.stdout
    assert '{"status":"DEMO"}' in result.stdout


def test_bitbucket_api_verbose_redacts_known_secrets_outside_headers(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [
            f"{COMPARE_CHANGES}?marker=example-user-id",
            "--verbose",
        ],
        [make_response("example-user-id")],
    )

    assert result.exit_code == 0
    assert "example-user-id" not in result.stdout
    assert result.stdout.count("REDACTED") >= 2


def test_bitbucket_api_verbose_redacts_echoed_command_header_secrets(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [
            COMPARE_CHANGES,
            "-H",
            "Authorization: Bearer example response",
            "--verbose",
        ],
        [
            make_response(
                "echoed Bearer example response",
                headers={"X-Echo": "Bearer example response"},
            )
        ],
    )

    assert result.exit_code == 0
    assert "Bearer example response" not in result.stdout
    assert "< X-Echo: REDACTED" in result.stdout
    assert "echoed REDACTED" in result.stdout


def test_redact_text_removes_url_encoded_secret_values() -> None:
    value = "?first=example+response&second=feature%2FDEMO-1234%2Fexample-change"

    redacted = api_module._redact_text(
        value,
        {"example response", "feature/DEMO-1234/example-change"},
    )

    assert redacted == "?first=REDACTED&second=REDACTED"


def test_bitbucket_api_redacts_known_secrets_from_network_errors(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES],
        [],
        error=OSError("example response: example-user-id"),
    )

    assert result.exit_code == 1
    assert "example-user-id" not in result.stderr
    assert "example response: REDACTED" in result.stderr


def test_bitbucket_api_redacts_command_header_secrets_from_network_errors(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "-H", "Authorization: Bearer example response"],
        [],
        error=OSError("request failed for Bearer example response"),
    )

    assert result.exit_code == 1
    assert "Bearer example response" not in result.stderr
    assert "request failed for REDACTED" in result.stderr


def test_bitbucket_api_rejects_control_characters_in_headers_before_request(monkeypatch) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "-H", "Authorization: Bearer example response\nDEMO"],
        [],
    )

    assert result.exit_code == 1
    assert provider.calls == []
    assert "Bearer example response" not in result.stderr
    assert "control characters" in result.stderr


@pytest.mark.parametrize(
    "header",
    [
        "Authorization Bearer example response",
        ": Bearer example response",
    ],
)
def test_bitbucket_api_header_format_errors_do_not_echo_values(monkeypatch, header: str) -> None:
    result, provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "-H", header],
        [],
    )

    assert result.exit_code == 1
    assert provider.calls == []
    assert "Bearer example response" not in result.stderr
    assert "header" in result.stderr


def test_bitbucket_api_verbose_http_error_exits_one(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, "--verbose"],
        [
            make_response(
                {"errors": [{"message": "example response"}]},
                status=404,
                reason="Not Found",
            )
        ],
    )

    assert result.exit_code == 1
    assert "< HTTP/1.1 404 Not Found" in result.stdout
    assert result.stderr == "atlassian: example response (HTTP 404)\n"


@pytest.mark.parametrize("jq_args", [[], ["--jq", ".values[]"]])
def test_bitbucket_api_http_error_preserves_body_and_exits_one(monkeypatch, jq_args) -> None:
    body = {"errors": [{"message": "example response"}]}
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES, *jq_args],
        [make_response(body, status=404, reason="Not Found")],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == body
    assert result.stderr == "atlassian: example response (HTTP 404)\n"


def test_bitbucket_api_network_error_exits_one(monkeypatch) -> None:
    result, _provider = invoke_api(
        monkeypatch,
        [COMPARE_CHANGES],
        [],
        error=OSError("example response"),
    )

    assert result.exit_code == 1
    assert "example response" in result.stderr
