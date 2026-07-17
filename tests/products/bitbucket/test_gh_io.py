import os
from io import BytesIO, StringIO, TextIOWrapper
from subprocess import CompletedProcess

import pytest

from atlassian_cli.products.bitbucket.gh_compat import io as io_module
from atlassian_cli.products.bitbucket.gh_compat.io import (
    can_prompt,
    color_enabled,
    open_browser,
    page_output,
    stdout_is_tty,
    stream_output,
    terminal_width,
)

PR_URL = "https://bitbucket.example.com/projects/DEMO/repos/example-repo/pull-requests/1234"


def test_terminal_width_uses_current_terminal_size(monkeypatch) -> None:
    monkeypatch.setattr(
        io_module.shutil,
        "get_terminal_size",
        lambda **_kwargs: os.terminal_size((117, 40)),
    )

    assert terminal_width() == 117


def test_force_tty_uses_only_atlassian_namespace() -> None:
    assert stdout_is_tty(lambda: False, {"ATLASSIAN_FORCE_TTY": "1"}) is True
    assert stdout_is_tty(lambda: False, {"ATLASSIAN_FORCE_TTY": ""}) is False
    assert stdout_is_tty(lambda: False, {"GH_FORCE_TTY": "1"}) is False


def test_prompt_requires_both_streams_and_honors_product_namespace() -> None:
    assert can_prompt(lambda: True, lambda: True, {}) is True
    assert can_prompt(lambda: False, lambda: True, {}) is False
    assert can_prompt(lambda: True, lambda: False, {}) is False
    assert (
        can_prompt(
            lambda: True,
            lambda: True,
            {"ATLASSIAN_PROMPT_DISABLED": ""},
        )
        is False
    )
    assert (
        can_prompt(
            lambda: True,
            lambda: True,
            {"GH_PROMPT_DISABLED": "1"},
        )
        is True
    )


def test_prompt_uses_effective_forced_stdout_tty() -> None:
    assert (
        can_prompt(
            lambda: True,
            lambda: False,
            {"ATLASSIAN_FORCE_TTY": "1"},
        )
        is True
    )


@pytest.mark.parametrize(
    ("tty", "env", "expected"),
    [
        (True, {}, True),
        (False, {}, False),
        (True, {"NO_COLOR": ""}, False),
        (True, {"CLICOLOR": "0"}, False),
        (True, {"CLICOLOR": "1"}, True),
        (True, {"GH_COLOR": "never"}, True),
    ],
)
def test_color_enabled_honors_only_standard_color_controls(
    tty: bool, env: dict[str, str], expected: bool
) -> None:
    assert color_enabled(tty, env) is expected


def test_browser_precedence_appends_url_without_shell() -> None:
    calls = []
    open_browser(
        PR_URL,
        env={"ATLASSIAN_BROWSER": "echo --new-window", "BROWSER": "echo --fallback"},
        run=lambda args: calls.append(args) or CompletedProcess(args, 0),
    )
    assert calls == [["echo", "--new-window", PR_URL]]


def test_browser_replaces_placeholder_without_appending_url() -> None:
    calls = []
    open_browser(
        PR_URL,
        env={"ATLASSIAN_BROWSER": "echo --url=%s"},
        run=lambda args: calls.append(args) or CompletedProcess(args, 0),
    )
    assert calls == [["echo", f"--url={PR_URL}"]]


def test_empty_product_browser_falls_back_to_standard_browser() -> None:
    calls = []
    open_browser(
        PR_URL,
        env={"ATLASSIAN_BROWSER": "", "BROWSER": "echo --fallback"},
        run=lambda args: calls.append(args) or CompletedProcess(args, 0),
    )
    assert calls == [["echo", "--fallback", PR_URL]]


def test_unconfigured_browser_uses_platform_default_and_ignores_gh() -> None:
    calls = []
    open_browser(
        PR_URL,
        env={"GH_BROWSER": "echo --wrong"},
        browser_open=lambda url: calls.append(url) or True,
    )
    assert calls == [PR_URL]


def test_browser_launch_failure_is_not_hidden() -> None:
    def fail(_args: list[str]) -> CompletedProcess:
        raise OSError("example browser failure")

    with pytest.raises(OSError, match="example browser failure"):
        open_browser(PR_URL, env={"ATLASSIAN_BROWSER": "example-browser"}, run=fail)


def test_pager_precedence_writes_content_to_stdin() -> None:
    calls = []
    page_output(
        "example response\n",
        tty=True,
        env={"ATLASSIAN_PAGER": "cat -n", "PAGER": "cat"},
        error_prefix="error starting pager",
        run=lambda args, text: calls.append((args, text)) or CompletedProcess(args, 0),
    )
    assert calls == [(["cat", "-n"], "example response\n")]


def test_stream_output_writes_binary_chunks_without_transcoding() -> None:
    buffer = BytesIO()
    stdout = TextIOWrapper(buffer, encoding="utf-8")

    stream_output(
        [b"\xff\x00", "DEMO"],
        tty=False,
        env={},
        error_prefix="error starting pager",
        stdout=stdout,
    )

    assert buffer.getvalue() == b"\xff\x00DEMO"


def test_stream_output_uses_one_pager_for_all_chunks(monkeypatch) -> None:
    calls = []

    class FakeStdin:
        def __init__(self) -> None:
            self.value = bytearray()

        def write(self, value: bytes) -> None:
            self.value.extend(value)

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = FakeStdin()

        def wait(self) -> int:
            return 0

    process = FakeProcess()

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(io_module.subprocess, "Popen", fake_popen)
    stream_output(
        [b"DEMO", b"-1"],
        tty=True,
        env={"ATLASSIAN_PAGER": "cat -n"},
        error_prefix="error starting pager",
    )

    assert len(calls) == 1
    assert calls[0][0] == ["cat", "-n"]
    assert bytes(process.stdin.value) == b"DEMO-1"


def test_stream_output_ignores_broken_pipe_while_closing_pager(monkeypatch) -> None:
    class ClosedStdin:
        def write(self, _value: bytes) -> None:
            raise BrokenPipeError

        def flush(self) -> None:
            pass

        def close(self) -> None:
            raise BrokenPipeError

    class ClosedProcess:
        stdin = ClosedStdin()

        @staticmethod
        def wait() -> int:
            return 0

    monkeypatch.setattr(
        io_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: ClosedProcess(),
    )

    stream_output(
        [b"example response"],
        tty=True,
        env={"ATLASSIAN_PAGER": "example-pager"},
        error_prefix="error starting pager",
    )


def test_empty_product_pager_falls_back_to_standard_pager() -> None:
    calls = []
    page_output(
        "example response\n",
        tty=True,
        env={"ATLASSIAN_PAGER": "", "PAGER": "cat"},
        error_prefix="error starting pager",
        run=lambda args, text: calls.append((args, text)) or CompletedProcess(args, 0),
    )
    assert calls == [(["cat"], "example response\n")]


def test_default_less_is_used_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(io_module.shutil, "which", lambda command: "/usr/bin/less")
    page_output(
        "example response\n",
        tty=True,
        env={"GH_PAGER": "cat --wrong"},
        error_prefix="error starting pager",
        run=lambda args, text: calls.append((args, text)) or CompletedProcess(args, 0),
    )
    assert calls == [(["less", "-FRX"], "example response\n")]


def test_pager_startup_failure_reports_error_then_writes_directly() -> None:
    stdout = StringIO()
    stderr = StringIO()

    def fail(_args: list[str], _text: str) -> CompletedProcess:
        raise OSError("example pager failure")

    page_output(
        "example response\n",
        tty=True,
        env={"ATLASSIAN_PAGER": "example-pager"},
        error_prefix="failed to start pager",
        run=fail,
        stdout=stdout,
        stderr=stderr,
    )

    assert stderr.getvalue() == "failed to start pager: example pager failure\n"
    assert stdout.getvalue() == "example response\n"


def test_pager_nonzero_exit_reports_error_then_writes_directly() -> None:
    stdout = StringIO()
    stderr = StringIO()

    page_output(
        "example response\n",
        tty=True,
        env={"ATLASSIAN_PAGER": "cat"},
        error_prefix="error starting pager",
        run=lambda args, _text: CompletedProcess(args, 1),
        stdout=stdout,
        stderr=stderr,
    )

    assert "error starting pager:" in stderr.getvalue()
    assert "non-zero exit status 1" in stderr.getvalue()
    assert stdout.getvalue() == "example response\n"


def test_non_tty_writes_directly_without_starting_pager() -> None:
    stdout = StringIO()

    def unexpected(_args: list[str], _text: str) -> CompletedProcess:
        pytest.fail("pager started")

    page_output(
        "example response\n",
        tty=False,
        env={"ATLASSIAN_PAGER": "example-pager", "GH_PAGER": "example-wrong"},
        error_prefix="error starting pager",
        run=unexpected,
        stdout=stdout,
    )
    assert stdout.getvalue() == "example response\n"


def test_missing_default_pager_writes_directly_and_ignores_gh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = StringIO()
    monkeypatch.setattr(io_module.shutil, "which", lambda command: None)
    page_output(
        "example response\n",
        tty=True,
        env={"GH_PAGER": "example-wrong"},
        error_prefix="error starting pager",
        stdout=stdout,
    )
    assert stdout.getvalue() == "example response\n"
