from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlsplit

import click
import jq
import typer
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import JsonLexer
from typer._click.exceptions import UsageError as TyperUsageError
from typer.core import TyperCommand

from atlassian_cli.products.bitbucket.api_fields import fill_placeholders, parse_api_fields
from atlassian_cli.products.bitbucket.commands.pr import resolve_repository
from atlassian_cli.products.bitbucket.gh_compat.auth import require_primary_auth
from atlassian_cli.products.bitbucket.gh_compat.exit_policy import run_gh_read
from atlassian_cli.products.bitbucket.gh_compat.io import (
    color_enabled,
    page_output,
    stdout_is_tty,
)
from atlassian_cli.products.bitbucket.gh_compat.selectors import ServerIdentity
from atlassian_cli.products.bitbucket.services.api import (
    ApiRequest,
    BitbucketApiService,
    normalize_api_endpoint,
)
from atlassian_cli.products.factory import build_provider


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
            raise ValueError(f"header {value!r} requires a value separated by ':'")
        name, header_value = value.split(":", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"invalid header: {value!r}")
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

    def __call__(self, name: str) -> str:
        if self._resolution is None:
            server = ServerIdentity.from_url(self.context.url)
            self._resolution = resolve_repository(server)
        if name == "project":
            return self._resolution.repository.project_key
        if name == "repo":
            return self._resolution.repository.repo_slug
        if name == "branch" and self._resolution.current_branch:
            return self._resolution.current_branch
        if name == "branch":
            raise ValueError(
                "unable to determine an appropriate value for the 'branch' placeholder"
            )
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


def _raw_body(response, *, color: bool) -> str:
    if response.status_code == 204:
        return ""
    text = response.text
    if color and text and _is_json_response(response):
        return highlight(text, JsonLexer(), TerminalFormatter()).rstrip("\n")
    return text


def _format_jq_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _render_jq(response, expression: str) -> str:
    try:
        payload = response.json()
        results = jq.compile(expression).input_value(payload).all()
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    return "".join(f"{_format_jq_value(value)}\n" for value in results)


def _secret_values(context) -> set[str]:
    auth = context.auth
    return {
        value
        for value in (
            auth.password,
            auth.token,
            *auth.headers.values(),
        )
        if value
    }


def _redacted_header(name: str, value: str, secrets: set[str]) -> str:
    secret_names = {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "accesstoken",
        "x-api-key",
    }
    if name.lower() in secret_names or any(secret in value for secret in secrets):
        return "REDACTED"
    return value


def _render_verbose(response, *, secrets: set[str]) -> str:
    request = response.request
    parsed = urlsplit(request.url)
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    lines = [
        f"* Request to {request.url}",
        f"> {request.method} {path} HTTP/1.1",
        f"> Host: {parsed.netloc}",
    ]
    lines.extend(
        f"> {name}: {_redacted_header(name, value, secrets)}"
        for name, value in request.headers.items()
    )
    if request.body:
        body = request.body.decode() if isinstance(request.body, bytes) else str(request.body)
        lines.extend([">", body])

    lines.extend(["", f"< HTTP/{_http_version(response)} {response.status_code} {response.reason}"])
    lines.extend(
        f"< {name}: {_redacted_header(name, response.headers[name], secrets)}"
        for name in sorted(response.headers, key=str.lower)
    )
    lines.extend(["", response.text])
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


def _write_output(text: str, *, silent: bool) -> None:
    if not text or silent:
        return
    tty = stdout_is_tty(sys.stdout.isatty, os.environ)
    page_output(
        text,
        tty=tty,
        env=os.environ,
        error_prefix="failed to start pager",
    )


def _render_responses(
    responses: Iterable[object],
    *,
    context,
    include: bool,
    jq_expression: str | None,
    silent: bool,
    slurp: bool,
    verbose: bool,
) -> None:
    tty = stdout_is_tty(sys.stdout.isatty, os.environ)
    color = color_enabled(tty, os.environ)
    chunks: list[str] = []
    slurped: list[object] = []
    secrets = _secret_values(context) if verbose else set()

    for index, response in enumerate(responses):
        if verbose:
            if index:
                chunks.append("\n")
            chunks.append(_render_verbose(response, secrets=secrets))
            if response.status_code >= 300:
                _write_output("".join(chunks), silent=False)
                typer.echo(f"atlassian: {_error_message(response)}", err=True)
                raise typer.Exit(1)
        else:
            if include:
                if index:
                    chunks.append("\n")
                chunks.append(_response_headers(response))
            if response.status_code >= 300:
                chunks.append(_raw_body(response, color=color))
                _write_output("".join(chunks), silent=False)
                typer.echo(f"atlassian: {_error_message(response)}", err=True)
                raise typer.Exit(1)
            if response.status_code == 204:
                continue
            if slurp:
                try:
                    slurped.append(response.json())
                except ValueError as exc:
                    raise ValueError("response body is not valid JSON") from exc
            elif jq_expression is not None:
                chunks.append(_render_jq(response, jq_expression))
            elif not silent:
                chunks.append(_raw_body(response, color=color))

    if slurp and not silent:
        chunks.append(json.dumps(slurped, ensure_ascii=False, separators=(",", ":")))
    _write_output("".join(chunks), silent=False)


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
        include=include,
        jq_expression=jq_expression,
        silent=silent,
        slurp=slurp,
        verbose=verbose,
    )


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
