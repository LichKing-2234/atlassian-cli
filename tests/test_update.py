import json
from pathlib import Path

from typer.testing import CliRunner

import atlassian_cli.commands.update as update_command
import atlassian_cli.update as update_module
from atlassian_cli.cli import app
from atlassian_cli.update import (
    InstallResult,
    ReleaseInfo,
    UpdateInfo,
    compare_versions,
    default_install_dir,
    fetch_latest_release,
    install_script_url_for_tag,
    normalize_tag,
)

runner = CliRunner()


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_normalize_tag_accepts_tag_or_plain_version() -> None:
    assert normalize_tag("v0.2.0") == "v0.2.0"
    assert normalize_tag("0.2.0") == "v0.2.0"


def test_install_script_url_is_pinned_to_target_tag() -> None:
    assert (
        install_script_url_for_tag("0.2.0")
        == "https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/v0.2.0/install.sh"
    )


def test_compare_versions_handles_release_and_prerelease_ordering() -> None:
    assert compare_versions("0.2.0", "0.1.0") > 0
    assert compare_versions("0.2.0-rc.2", "0.2.0-rc.1") > 0
    assert compare_versions("0.2.0", "0.2.0-rc.1") > 0
    assert compare_versions("v0.2.0", "0.2.0") == 0


def test_fetch_latest_release_parses_github_payload(monkeypatch) -> None:
    def fake_urlopen(url, timeout):
        assert url == "https://example.invalid/latest"
        assert timeout == 10
        return FakeResponse(
            {
                "tag_name": "v0.2.0",
                "html_url": "https://github.com/DEMO/example-repo/releases/tag/v0.2.0",
            }
        )

    monkeypatch.setattr(update_module, "urlopen", fake_urlopen)

    release = fetch_latest_release(api_url="https://example.invalid/latest")

    assert release == ReleaseInfo(
        tag="v0.2.0",
        version="0.2.0",
        url="https://github.com/DEMO/example-repo/releases/tag/v0.2.0",
    )


def test_default_install_dir_uses_env_override(tmp_path: Path) -> None:
    install_dir = tmp_path / "bin"

    assert default_install_dir(environ={"ATLASSIAN_INSTALL_DIR": str(install_dir)}) == install_dir


def test_default_install_dir_recovers_launcher_dir_from_bundle_path(tmp_path: Path) -> None:
    executable = tmp_path / "bin" / ".atlassian-cli" / "atlassian" / "atlassian"
    executable.parent.mkdir(parents=True)
    executable.write_text("")

    assert (
        default_install_dir(environ={}, executable=str(executable), frozen=True) == tmp_path / "bin"
    )


def test_default_install_dir_for_python_install_uses_local_bin(tmp_path: Path) -> None:
    executable = tmp_path / ".venv" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.write_text("")

    assert (
        default_install_dir(
            environ={},
            executable=str(executable),
            frozen=False,
            home=tmp_path / "home",
        )
        == tmp_path / "home" / ".local" / "bin"
    )


def test_default_install_dir_for_frozen_build_uses_launcher_from_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "runtime" / "atlassian"
    executable.parent.mkdir(parents=True)
    executable.write_text("")
    launcher = tmp_path / "bin" / "atlassian"
    launcher.parent.mkdir()
    launcher.write_text("")

    monkeypatch.setattr(update_module.shutil, "which", lambda name: str(launcher))

    assert (
        default_install_dir(environ={}, executable=str(executable), frozen=True) == launcher.parent
    )


def test_default_install_dir_for_frozen_build_without_launcher_uses_executable_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "runtime" / "atlassian"
    executable.parent.mkdir(parents=True)
    executable.write_text("")

    monkeypatch.setattr(update_module.shutil, "which", lambda name: None)

    assert (
        default_install_dir(environ={}, executable=str(executable), frozen=True)
        == executable.parent
    )


def test_run_install_script_sets_version_and_install_dir(tmp_path: Path, monkeypatch) -> None:
    install_dir = tmp_path / "bin"
    calls: dict = {}
    download_calls: dict = {}

    monkeypatch.setenv("ATLASSIAN_TEST_PARENT_ENV", "preserved")

    def fake_download_install_script(script_url):
        download_calls["script_url"] = script_url
        return "#!/bin/sh\necho install fixture\n"

    monkeypatch.setattr(update_module, "_download_install_script", fake_download_install_script)

    def fake_run(args, env, capture_output, text, check):
        calls["args"] = args
        calls["env"] = env
        calls["capture_output"] = capture_output
        calls["text"] = text
        calls["check"] = check
        assert Path(args[1]).read_text(encoding="utf-8") == "#!/bin/sh\necho install fixture\n"
        return type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": "installed v0.2.0 to fixture\n",
                "stderr": "",
            },
        )()

    monkeypatch.setattr(update_module.subprocess, "run", fake_run)

    result = update_module.run_install_script(
        version="0.2.0",
        install_dir=install_dir,
        env={"PATH": "/bin"},
    )

    assert (
        download_calls["script_url"]
        == "https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/v0.2.0/install.sh"
    )
    assert calls["args"][0] == "sh"
    assert calls["env"]["ATLASSIAN_TEST_PARENT_ENV"] == "preserved"
    assert calls["env"]["PATH"] == "/bin"
    assert calls["env"]["INSTALL_VERSION"] == "v0.2.0"
    assert calls["env"]["INSTALL_DIR"] == str(install_dir)
    assert calls["capture_output"] is True
    assert calls["text"] is True
    assert calls["check"] is False
    assert result.version == "v0.2.0"
    assert result.updated is True


def test_update_check_outputs_latest_release_json(monkeypatch) -> None:
    monkeypatch.setattr(
        update_command,
        "get_update_info",
        lambda current_version: UpdateInfo(
            current_version=current_version,
            latest=ReleaseInfo(tag="v0.2.0", version="0.2.0"),
            update_available=True,
        ),
    )

    result = runner.invoke(app, ["update", "check", "--output", "json"])

    assert result.exit_code == 0
    assert '"current_version": "0.1.0"' in result.stdout
    assert '"latest_tag": "v0.2.0"' in result.stdout
    assert '"update_available": true' in result.stdout


def test_update_commands_do_not_load_product_config(monkeypatch) -> None:
    def fail_load_config(path):
        raise AssertionError("update commands must not load Atlassian product config")

    monkeypatch.setattr("atlassian_cli.cli.load_config", fail_load_config)
    monkeypatch.setattr(
        update_command,
        "get_update_info",
        lambda current_version: UpdateInfo(
            current_version=current_version,
            latest=ReleaseInfo(tag="v0.1.0", version="0.1.0"),
            update_available=False,
        ),
    )

    result = runner.invoke(app, ["--config-file", "/tmp/missing.toml", "update", "check"])

    assert result.exit_code == 0
    assert "up to date" in result.stdout.lower()


def test_update_install_passes_selected_options(monkeypatch, tmp_path: Path) -> None:
    install_dir = tmp_path / "bin"
    calls: dict = {}

    def fake_install_update(**kwargs):
        calls.update(kwargs)
        return InstallResult(
            version="v0.2.0",
            install_dir=install_dir,
            updated=True,
            message="installed v0.2.0 to fixture",
        )

    monkeypatch.setattr(update_command, "install_update", fake_install_update)

    result = runner.invoke(
        app,
        [
            "update",
            "install",
            "--version",
            "0.2.0",
            "--install-dir",
            str(install_dir),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert calls == {
        "current_version": "0.1.0",
        "version": "0.2.0",
        "install_dir": install_dir,
        "force": True,
    }
    assert "installed v0.2.0" in result.stdout
