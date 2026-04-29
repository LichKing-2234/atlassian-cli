import subprocess

import pytest

from atlassian_cli.config.header_substitution import (
    run_header_command,
    substitute_header_commands,
)
from atlassian_cli.core.errors import ConfigError


def test_substitute_header_commands_replaces_command_output() -> None:
    resolved = substitute_header_commands(
        value="Bearer $(example-oauth token)",
        source="[headers]",
        header_name="Authorization",
        runner=lambda command: "oauth-token" if command == "example-oauth token" else "",
    )

    assert resolved == "Bearer oauth-token"


def test_substitute_header_commands_supports_multiple_substitutions() -> None:
    outputs = {
        "whoami": "alice",
        "example-oauth token": "oauth-token",
    }
    resolved = substitute_header_commands(
        value="User $(whoami) Token $(example-oauth token)",
        source="[profiles.code.headers]",
        header_name="X-Debug",
        runner=lambda command: outputs[command],
    )

    assert resolved == "User alice Token oauth-token"


def test_substitute_header_commands_rejects_malformed_syntax() -> None:
    with pytest.raises(ConfigError, match="Malformed"):
        substitute_header_commands(
            value="$(example-oauth token",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "ignored",
        )


def test_substitute_header_commands_rejects_empty_command_body() -> None:
    with pytest.raises(ConfigError, match="Malformed"):
        substitute_header_commands(
            value="prefix $() suffix",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "ignored",
        )


def test_substitute_header_commands_rejects_nested_commands() -> None:
    with pytest.raises(ConfigError, match="Malformed"):
        substitute_header_commands(
            value="$(echo $(whoami))",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "ignored",
        )


def test_substitute_header_commands_rejects_empty_output() -> None:
    with pytest.raises(ConfigError, match="empty output"):
        substitute_header_commands(
            value="$(example-oauth token)",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "   ",
        )


def test_substitute_header_commands_rejects_multiline_output() -> None:
    with pytest.raises(ConfigError, match="single line"):
        substitute_header_commands(
            value="$(example-oauth token)",
            source="[headers]",
            header_name="accessToken",
            runner=lambda command: "line-one\nline-two",
        )


def test_run_header_command_raises_for_non_zero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=7,
            stdout="",
            stderr="oauth failed",
        ),
    )

    with pytest.raises(ConfigError, match="exit code 7"):
        run_header_command("example-oauth token")
