from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote, quote_plus, urlsplit

import click
import jq
import typer
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import JsonLexer
from typer._click.exceptions import UsageError as TyperUsageError
from typer.core import TyperCommand

from atlassian_cli.products.bitbucket.api_fields import (
    fill_placeholders,
    parse_api_fields,
    validate_api_fields,
    validate_placeholders,
)
from atlassian_cli.products.bitbucket.commands.pr import resolve_repository
from atlassian_cli.products.bitbucket.gh_compat.auth import require_primary_auth
from atlassian_cli.products.bitbucket.gh_compat.exit_policy import run_gh_read
from atlassian_cli.products.bitbucket.gh_compat.io import (
    color_enabled,
    stdout_is_tty,
    stream_output,
)
from atlassian_cli.products.bitbucket.gh_compat.repository_context import GitRepositoryContext
from atlassian_cli.products.bitbucket.gh_compat.selectors import ServerIdentity
from atlassian_cli.products.bitbucket.services.api import (
    ApiRequest,
    BitbucketApiService,
    normalize_api_endpoint,
)
from atlassian_cli.products.factory import build_provider

_SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "accesstoken",
    "x-api-key",
}


class GhApiCommand(TyperCommand):
    @staticmethod
    def _normalize_usage_piece(value: str) -> str:
        return "<endpoint>" if value == "{<endpoint>}" else value

    def collect_usage_pieces(self, ctx) -> list[str]:
        return [self._normalize_usage_piece(value) for value in super().collect_usage_pieces(ctx)]

    def parse_args(self, ctx, args):
        try:
            return super().parse_args(ctx, args)
        except (click.UsageError, TyperUsageError) as exc:
            exc.exit_code = 1
            raise


def _parameter_is_explicit(ctx: typer.Context, name: str) -> bool:
    source = ctx.get_parameter_source(name)
    return source is not None and source.name == "COMMANDLINE"


def _parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    names: dict[str, str] = {}
    for value in values:
        if ":" not in value:
            raise ValueError("header requires a value separated by ':'")
        name, header_value = value.split(":", 1)
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("header names and values cannot contain control characters")
        name = name.strip()
        if not name:
            raise ValueError("invalid header name")
        previous = names.get(name.lower())
        if previous is not None:
            del headers[previous]
        headers[name] = header_value.strip()
        names[name.lower()] = name
    return headers


def _validate_options(
    *,
    method: str,
    input_file: str | None,
    paginate: bool,
    slurp: bool,
    jq_expression: str | None,
    silent: bool,
    verbose: bool,
) -> None:
    if paginate and input_file is not None:
        raise ValueError("the `--paginate` option is not supported with `--input`")
    if paginate and method.upper() != "GET":
        raise ValueError("the `--paginate` option is not supported for non-GET requests")
    if slurp and not paginate:
        raise ValueError("`--paginate` required when passing `--slurp`")
    if slurp and jq_expression is not None:
        raise ValueError("the `--slurp` option is not supported with `--jq`")
    selected_outputs = sum((jq_expression is not None, silent, verbose))
    if selected_outputs > 1:
        raise ValueError("only one of `--jq`, `--silent`, or `--verbose` may be used")


def _read_input_file(value: str) -> bytes:
    if value != "-":
        return Path(value).read_bytes()
    stream = getattr(sys.stdin, "buffer", None)
    if stream is not None:
        return stream.read()
    return sys.stdin.read().encode()


class _ApiPlaceholderResolver:
    def __init__(self, context) -> None:
        self.context = context
        self._resolution = None
        self._snapshot = None
        self._branch: str | None = None
        self._branch_loaded = False

    def _git_snapshot(self):
        if self._snapshot is None:
            self._snapshot = GitRepositoryContext(Path.cwd()).read()
        return self._snapshot

    def __call__(self, name: str) -> str:
        if name == "branch":
            if not self._branch_loaded:
                if self._resolution is not None and self._resolution.current_branch:
                    self._branch = self._resolution.current_branch
                else:
                    self._branch = self._git_snapshot().current_branch
                self._branch_loaded = True
            if self._branch:
                return self._branch
            raise ValueError(
                "unable to determine an appropriate value for the 'branch' placeholder"
            )
        if self._resolution is None:
            server = ServerIdentity.from_url(self.context.url)
            self._resolution = resolve_repository(
                server,
                **({"snapshot": self._snapshot} if self._snapshot is not None else {}),
            )
        if name == "project":
            return self._resolution.repository.project_key
        if name == "repo":
            return self._resolution.repository.repo_slug
        raise ValueError(f"unknown placeholder: {name}")


def _http_version(response) -> str:
    version = getattr(getattr(response, "raw", None), "version", None)
    return {10: "1.0", 11: "1.1", 20: "2.0", 2: "2.0"}.get(version, "1.1")


def _response_headers(response) -> str:
    lines = [f"HTTP/{_http_version(response)} {response.status_code} {response.reason}"]
    lines.extend(
        f"{name}: {response.headers[name]}" for name in sorted(response.headers, key=str.lower)
    )
    return "\n".join(lines) + "\n\n"


def _is_json_response(response) -> bool:
    content_type = str(response.headers.get("Content-Type", ""))
    media_type = content_type.partition(";")[0].strip().lower()
    return media_type.endswith("/json") or media_type.endswith("+json")


def _raw_body(response, *, color: bool) -> bytes:
    if response.status_code == 204:
        return b""
    text = response.text
    if color and text and _is_json_response(response):
        return highlight(text, JsonLexer(), TerminalFormatter()).rstrip("\n").encode()
    return response.content


def _format_jq_value(value: object, *, tty: bool, color: bool) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if tty and isinstance(value, (dict, list)):
        rendered = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if color:
        return highlight(rendered, JsonLexer(), TerminalFormatter()).rstrip("\n")
    return rendered


def _render_jq(response, expression: str, *, tty: bool, color: bool) -> bytes:
    try:
        payload = response.json()
        results = jq.compile(expression).input_value(payload).all()
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    return "".join(
        f"{_format_jq_value(value, tty=tty, color=color)}\n" for value in results
    ).encode()


def _secret_values(context, request_headers: dict[str, str] | None = None) -> set[str]:
    auth = context.auth
    secrets = {
        value
        for value in (
            auth.password,
            auth.token,
            *auth.headers.values(),
        )
        if value
    }
    secrets.update(
        value
        for name, value in (request_headers or {}).items()
        if name.lower() in _SENSITIVE_HEADER_NAMES and value
    )
    return secrets


def _redact_text(value: str, secrets: set[str]) -> str:
    variants = {
        variant
        for secret in secrets
        for variant in (secret, quote(secret, safe=""), quote_plus(secret, safe=""))
        if variant
    }
    for secret in sorted(variants, key=len, reverse=True):
        value = value.replace(secret, "REDACTED")
    return value


def _redacted_header(name: str, value: str, secrets: set[str]) -> str:
    if name.lower() in _SENSITIVE_HEADER_NAMES:
        return "REDACTED"
    return _redact_text(value, secrets)


def _render_verbose(response, *, secrets: set[str]) -> str:
    request = response.request
    parsed = urlsplit(request.url)
    request_url = _redact_text(request.url, secrets)
    path = _redact_text(
        parsed.path + (f"?{parsed.query}" if parsed.query else ""),
        secrets,
    )
    lines = [
        f"* Request to {request_url}",
        f"> {request.method} {path} HTTP/1.1",
        f"> Host: {_redact_text(parsed.netloc, secrets)}",
    ]
    lines.extend(
        f"> {name}: {_redacted_header(name, value, secrets)}"
        for name, value in request.headers.items()
    )
    if request.body:
        body = (
            request.body.decode(errors="replace")
            if isinstance(request.body, bytes)
            else str(request.body)
        )
        lines.extend([">", body])

    lines.extend(["", f"< HTTP/{_http_version(response)} {response.status_code} {response.reason}"])
    lines.extend(
        f"< {name}: {_redacted_header(name, response.headers[name], secrets)}"
        for name in sorted(response.headers, key=str.lower)
    )
    lines.extend(["", _redact_text(response.text, secrets)])
    return "\n".join(lines)


def _error_message(response) -> str:
    message = ""
    if _is_json_response(response):
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            errors = payload.get("errors")
            if isinstance(errors, list):
                messages = [
                    item.get("message")
                    for item in errors
                    if isinstance(item, dict) and isinstance(item.get("message"), str)
                ]
                message = "\n".join(value for value in messages if value)
    if not message:
        message = response.reason or f"HTTP {response.status_code}"
    return f"{message} (HTTP {response.status_code})"


def _response_chunks(
    responses: Iterable[object],
    *,
    context,
    request_headers: dict[str, str],
    include: bool,
    jq_expression: str | None,
    silent: bool,
    slurp: bool,
    verbose: bool,
) -> Iterable[bytes]:
    tty = stdout_is_tty(sys.stdout.isatty, os.environ)
    color = color_enabled(tty, os.environ)
    secrets = _secret_values(context, request_headers)
    slurp_started = False

    for index, response in enumerate(responses):
        if verbose:
            if index:
                yield b"\n"
            yield _render_verbose(response, secrets=secrets).encode()
            if response.status_code >= 300:
                typer.echo(
                    f"atlassian: {_redact_text(_error_message(response), secrets)}",
                    err=True,
                )
                raise typer.Exit(1)
        else:
            if include:
                if index:
                    yield b"\n"
                yield _response_headers(response).encode()
            if response.status_code >= 300:
                yield _raw_body(response, color=color)
                typer.echo(
                    f"atlassian: {_redact_text(_error_message(response), secrets)}",
                    err=True,
                )
                raise typer.Exit(1)
            if response.status_code == 204:
                continue
            if slurp and not silent:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ValueError("response body is not valid JSON") from exc
                yield b"," if slurp_started else b"["
                yield json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
                slurp_started = True
            elif jq_expression is not None:
                yield _render_jq(response, jq_expression, tty=tty, color=color)
            elif not silent:
                yield _raw_body(response, color=color)

    if slurp and not silent:
        yield b"]" if slurp_started else b"[]"


def _render_responses(
    responses: Iterable[object],
    *,
    context,
    request_headers: dict[str, str],
    include: bool,
    jq_expression: str | None,
    silent: bool,
    slurp: bool,
    verbose: bool,
) -> None:
    tty = stdout_is_tty(sys.stdout.isatty, os.environ)
    stream_output(
        _response_chunks(
            responses,
            context=context,
            request_headers=request_headers,
            include=include,
            jq_expression=jq_expression,
            silent=silent,
            slurp=slurp,
            verbose=verbose,
        ),
        tty=tty and not silent,
        env=os.environ,
        error_prefix="failed to start pager",
    )


def _api_run(
    *,
    ctx: typer.Context,
    endpoint: str,
    typed_fields: list[str],
    headers: list[str],
    include: bool,
    input_file: str | None,
    jq_expression: str | None,
    method: str,
    paginate: bool,
    raw_fields: list[str],
    silent: bool,
    slurp: bool,
    verbose: bool,
) -> None:
    method_explicit = _parameter_is_explicit(ctx, "method")
    resolved_method = method.upper()
    if not method_explicit and (typed_fields or raw_fields or input_file is not None):
        resolved_method = "POST"

    _validate_options(
        method=resolved_method,
        input_file=input_file,
        paginate=paginate,
        slurp=slurp,
        jq_expression=jq_expression,
        silent=silent,
        verbose=verbose,
    )
    normalize_api_endpoint(endpoint)
    validate_placeholders(endpoint)
    validate_api_fields(raw_fields, typed_fields)
    parsed_headers = _parse_headers(headers)

    context = ctx.obj
    require_primary_auth(context.auth)
    resolver = _ApiPlaceholderResolver(context)
    resolved_endpoint = fill_placeholders(endpoint, resolver)
    fields = parse_api_fields(
        raw_fields,
        typed_fields,
        resolver=resolver,
        stdin=sys.stdin,
    )
    input_body = _read_input_file(input_file) if input_file is not None else None

    try:
        responses = BitbucketApiService(build_provider(context)).iter_responses(
            ApiRequest(
                endpoint=resolved_endpoint,
                method=resolved_method,
                headers=parsed_headers,
                fields=fields,
                input_body=input_body,
            ),
            paginate=paginate,
        )
        _render_responses(
            responses,
            context=context,
            request_headers=parsed_headers,
            include=include,
            jq_expression=jq_expression,
            silent=silent,
            slurp=slurp,
            verbose=verbose,
        )
    except typer.Exit:
        raise
    except Exception as exc:
        redacted = _redact_text(str(exc), _secret_values(context, parsed_headers))
        if redacted == str(exc):
            raise
        raise ValueError(redacted) from None


def api_command(
    ctx: typer.Context,
    endpoint: str = typer.Argument(..., metavar="<endpoint>"),
    typed_fields: list[str] = typer.Option([], "--field", "-F", metavar="key=value"),
    headers: list[str] = typer.Option([], "--header", "-H", metavar="key:value"),
    include: bool = typer.Option(False, "--include", "-i"),
    input_file: str | None = typer.Option(None, "--input", metavar="file"),
    jq_expression: str | None = typer.Option(None, "--jq", "-q", metavar="expression"),
    method: str = typer.Option("GET", "--method", "-X", metavar="method"),
    paginate: bool = typer.Option(False, "--paginate"),
    raw_fields: list[str] = typer.Option([], "--raw-field", "-f", metavar="key=value"),
    silent: bool = typer.Option(False, "--silent"),
    slurp: bool = typer.Option(False, "--slurp"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    run_gh_read(
        lambda: _api_run(
            ctx=ctx,
            endpoint=endpoint,
            typed_fields=typed_fields,
            headers=headers,
            include=include,
            input_file=input_file,
            jq_expression=jq_expression,
            method=method,
            paginate=paginate,
            raw_fields=raw_fields,
            silent=silent,
            slurp=slurp,
            verbose=verbose,
        )
    )
