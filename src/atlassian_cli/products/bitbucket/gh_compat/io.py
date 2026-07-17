from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import webbrowser
from collections.abc import Callable, Iterable, Mapping
from subprocess import CompletedProcess
from typing import TextIO

Environment = Mapping[str, str]
BrowserRunner = Callable[[list[str]], CompletedProcess]
PagerRunner = Callable[[list[str], str], CompletedProcess]
OutputChunk = str | bytes


def _environment(env: Environment | None) -> Environment:
    return os.environ if env is None else env


def stdout_is_tty(isatty: Callable[[], bool], env: Environment | None = None) -> bool:
    environment = _environment(env)
    return bool(isatty()) or bool(environment.get("ATLASSIAN_FORCE_TTY"))


def can_prompt(
    stdin_isatty: Callable[[], bool],
    stdout_isatty: Callable[[], bool],
    env: Environment | None = None,
) -> bool:
    environment = _environment(env)
    if "ATLASSIAN_PROMPT_DISABLED" in environment:
        return False
    return bool(stdin_isatty()) and stdout_is_tty(stdout_isatty, environment)


def color_enabled(tty: bool, env: Environment | None = None) -> bool:
    environment = _environment(env)
    return bool(tty) and "NO_COLOR" not in environment and environment.get("CLICOLOR") != "0"


def terminal_width() -> int:
    return shutil.get_terminal_size(fallback=(80, 24)).columns


def _configured_command(environment: Environment, product_key: str, standard_key: str) -> str:
    product_value = environment.get(product_key, "")
    if product_value.strip():
        return product_value
    standard_value = environment.get(standard_key, "")
    return standard_value if standard_value.strip() else ""


def _run_browser(args: list[str]) -> CompletedProcess:
    return subprocess.run(args, check=False, shell=False)


def open_browser(
    url: str,
    *,
    env: Environment | None = None,
    run: BrowserRunner | None = None,
    browser_open: Callable[[str], object] | None = None,
) -> None:
    environment = _environment(env)
    command = _configured_command(environment, "ATLASSIAN_BROWSER", "BROWSER")
    if command:
        args = shlex.split(command)
        has_placeholder = any("%s" in item for item in args)
        if has_placeholder:
            args = [item.replace("%s", url) for item in args]
        else:
            args.append(url)
        result = (run or _run_browser)(args)
        result.check_returncode()
        return

    opened = (browser_open or webbrowser.open)(url)
    if opened is False:
        raise OSError("failed to open browser")


def _run_pager(args: list[str], text: str) -> CompletedProcess:
    return subprocess.run(args, input=text, text=True, check=False, shell=False)


def page_output(
    text: str,
    *,
    tty: bool,
    env: Environment | None,
    error_prefix: str,
    run: PagerRunner | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    if not tty:
        stdout.write(text)
        return

    environment = _environment(env)
    command = _configured_command(environment, "ATLASSIAN_PAGER", "PAGER")
    if command:
        try:
            args = shlex.split(command)
            result = (run or _run_pager)(args, text)
            result.check_returncode()
        except Exception as error:
            stderr.write(f"{error_prefix}: {error}\n")
            stdout.write(text)
        return

    if shutil.which("less"):
        try:
            result = (run or _run_pager)(["less", "-FRX"], text)
            result.check_returncode()
        except Exception as error:
            stderr.write(f"{error_prefix}: {error}\n")
            stdout.write(text)
        return

    stdout.write(text)


def _write_chunk(stdout: TextIO, chunk: OutputChunk) -> None:
    if isinstance(chunk, bytes):
        binary = getattr(stdout, "buffer", None)
        if binary is None:
            raise TypeError("binary output requires a byte-capable stdout")
        binary.write(chunk)
    else:
        stdout.write(chunk)
    stdout.flush()


def stream_output(
    chunks: Iterable[OutputChunk],
    *,
    tty: bool,
    env: Environment | None,
    error_prefix: str,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    if not tty:
        for chunk in chunks:
            _write_chunk(stdout, chunk)
        return

    environment = _environment(env)
    command = _configured_command(environment, "ATLASSIAN_PAGER", "PAGER")
    if command:
        args = shlex.split(command)
    elif shutil.which("less"):
        args = ["less", "-FRX"]
    else:
        for chunk in chunks:
            _write_chunk(stdout, chunk)
        return

    try:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, shell=False)
    except Exception as error:
        stderr.write(f"{error_prefix}: {error}\n")
        for chunk in chunks:
            _write_chunk(stdout, chunk)
        return

    assert process.stdin is not None
    try:
        for chunk in chunks:
            payload = chunk.encode() if isinstance(chunk, str) else chunk
            process.stdin.write(payload)
            process.stdin.flush()
    except BrokenPipeError:
        pass
    finally:
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass
        return_code = process.wait()
    if return_code:
        stderr.write(f"{error_prefix}: pager exited with status {return_code}\n")
