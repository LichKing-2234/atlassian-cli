import json
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import atlassian_cli.commands.update as update_command
import atlassian_cli.update as update_module
from atlassian_cli import __version__
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


def test_package_version_matches_pyproject() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    assert __version__ == pyproject["project"]["version"]


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


def test_install_script_url_uses_powershell_installer_on_windows() -> None:
    assert (
        install_script_url_for_tag("0.2.0", platform="win32")
        == "https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/v0.2.0/install.ps1"
    )


def test_compare_versions_handles_release_and_prerelease_ordering() -> None:
    assert compare_versions("0.2.0", "0.1.0") > 0
    assert compare_versions("0.2.0-rc.2", "0.2.0-rc.1") > 0
    assert compare_versions("0.2.0", "0.2.0-rc.1") > 0
    assert compare_versions("v0.2.0", "0.2.0") == 0


def test_fetch_latest_release_parses_github_payload(monkeypatch) -> None:
    def fake_urlopen(url, timeout, context):
        assert url == "https://example.invalid/latest"
        assert timeout == 10
        assert context is not None
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


def test_run_install_script_uses_powershell_on_windows(tmp_path: Path, monkeypatch) -> None:
    install_dir = tmp_path / "bin"
    calls: dict = {}
    download_calls: dict = {}

    monkeypatch.setattr(update_module.sys, "platform", "win32")
    monkeypatch.setattr(
        update_module.shutil,
        "which",
        lambda name: f"C:/Windows/System32/{name}.exe" if name == "pwsh" else None,
    )

    def fake_download_install_script(script_url):
        download_calls["script_url"] = script_url
        return 'Write-Output "install fixture"\n'

    monkeypatch.setattr(update_module, "_download_install_script", fake_download_install_script)

    def fake_run(args, env, capture_output, text, check):
        calls["args"] = args
        calls["env"] = env
        assert Path(args[-1]).read_text(encoding="utf-8") == 'Write-Output "install fixture"\n'
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
    )

    assert (
        download_calls["script_url"]
        == "https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/v0.2.0/install.ps1"
    )
    assert calls["args"] == [
        "C:/Windows/System32/pwsh.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        calls["args"][-1],
    ]
    assert calls["args"][-1].endswith("install.ps1")
    assert calls["env"]["INSTALL_VERSION"] == "v0.2.0"
    assert calls["env"]["INSTALL_DIR"] == str(install_dir)
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
    assert f'"current_version": "{__version__}"' in result.stdout
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
        "current_version": __version__,
        "version": "0.2.0",
        "install_dir": install_dir,
        "force": True,
    }
    assert "installed v0.2.0" in result.stdout


def test_auto_update_notice_reports_newer_release_and_records_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "update-check.json"

    monkeypatch.setattr(
        update_module,
        "fetch_latest_release",
        lambda timeout=2: ReleaseInfo(
            tag="v0.2.0",
            version="0.2.0",
            url="https://github.com/DEMO/example-repo/releases/tag/v0.2.0",
        ),
    )

    notice = update_module.check_for_update_notice(
        "0.1.0",
        state_path=state_file,
        now=1000,
        environ={},
    )

    assert notice is not None
    assert "atlassian-cli 0.1.0 can be updated to v0.2.0." in notice
    assert "Run: atlassian update install" in notice
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_checked_at"] == 1000
    assert state["latest_tag"] == "v0.2.0"


def test_auto_update_notice_skips_recent_check(monkeypatch, tmp_path: Path) -> None:
    state_file = tmp_path / "update-check.json"
    state_file.write_text(json.dumps({"last_checked_at": 1000}), encoding="utf-8")

    def fail_fetch(**kwargs):
        raise AssertionError("recent automatic checks must be throttled")

    monkeypatch.setattr(update_module, "fetch_latest_release", fail_fetch)

    notice = update_module.check_for_update_notice(
        "0.1.0",
        state_path=state_file,
        now=1000 + 60,
        environ={},
    )

    assert notice is None


def test_auto_update_notice_does_not_throttle_future_state(monkeypatch, tmp_path: Path) -> None:
    state_file = tmp_path / "update-check.json"
    state_file.write_text(json.dumps({"last_checked_at": 2000}), encoding="utf-8")
    calls = 0

    def fake_fetch_latest_release(timeout=2):
        nonlocal calls
        calls += 1
        return ReleaseInfo(tag="v0.2.0", version="0.2.0")

    monkeypatch.setattr(update_module, "fetch_latest_release", fake_fetch_latest_release)

    notice = update_module.check_for_update_notice(
        "0.1.0",
        state_path=state_file,
        now=1000,
        environ={},
    )

    assert calls == 1
    assert notice is not None


def test_auto_update_notice_respects_disable_env(monkeypatch, tmp_path: Path) -> None:
    def fail_fetch(**kwargs):
        raise AssertionError("disabled automatic checks must not fetch release metadata")

    monkeypatch.setattr(update_module, "fetch_latest_release", fail_fetch)

    notice = update_module.check_for_update_notice(
        "0.1.0",
        state_path=tmp_path / "update-check.json",
        now=1000,
        environ={"ATLASSIAN_DISABLE_UPDATE_CHECK": "1"},
    )

    assert notice is None


def test_auto_update_notice_records_failures_without_reporting(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "update-check.json"

    def fail_fetch(**kwargs):
        raise update_module.UpdateError("network unavailable")

    monkeypatch.setattr(update_module, "fetch_latest_release", fail_fetch)

    notice = update_module.check_for_update_notice(
        "0.1.0",
        state_path=state_file,
        now=1000,
        environ={},
    )

    assert notice is None
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_checked_at"] == 1000
    assert state["last_error"] == "network unavailable"


def test_auto_update_notice_suppresses_invalid_release_versions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "update-check.json"

    monkeypatch.setattr(
        update_module,
        "fetch_latest_release",
        lambda timeout=2: ReleaseInfo(tag="vbad", version="bad"),
    )

    notice = update_module.check_for_update_notice(
        "0.1.0",
        state_path=state_file,
        now=1000,
        environ={},
    )

    assert notice is None
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_checked_at"] == 1000
    assert state["last_error"] == "unsupported version format: bad"


def test_auto_update_notice_suppresses_unexpected_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "update-check.json"

    def fail_fetch(**kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(update_module, "fetch_latest_release", fail_fetch)

    notice = update_module.check_for_update_notice(
        "0.1.0",
        state_path=state_file,
        now=1000,
        environ={},
    )

    assert notice is None
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_checked_at"] == 1000
    assert state["last_error"] == "unexpected failure"


def test_cli_emits_auto_update_notice_to_stderr_for_interactive_human_command(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import atlassian_cli.cli as cli_module

    monkeypatch.setattr(cli_module, "_stderr_is_interactive", lambda: True)
    monkeypatch.setattr(
        cli_module,
        "check_for_update_notice",
        lambda current_version: (
            "atlassian-cli 0.1.7 can be updated to v0.2.0.\nRun: atlassian update install"
        ),
    )

    result = runner.invoke(
        app,
        [
            "init",
            "jira",
            "--config-file",
            str(tmp_path / "config.toml"),
            "--deployment",
            "server",
            "--url",
            "https://example.com",
            "--auth",
            "pat",
            "--token",
            "secret",
        ],
    )

    assert result.exit_code == 0
    assert "atlassian-cli 0.1.7 can be updated to v0.2.0." in result.stderr
    assert "Wrote [jira]" in result.stdout


def test_cli_ignores_unexpected_auto_update_notice_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import atlassian_cli.cli as cli_module

    monkeypatch.setattr(cli_module, "_stderr_is_interactive", lambda: True)

    def fail_check(current_version):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli_module, "check_for_update_notice", fail_check)

    result = runner.invoke(
        app,
        [
            "init",
            "jira",
            "--config-file",
            str(tmp_path / "config.toml"),
            "--deployment",
            "server",
            "--url",
            "https://example.com",
            "--auth",
            "pat",
            "--token",
            "secret",
        ],
    )

    assert result.exit_code == 0
    assert "Wrote [jira]" in result.stdout


def test_cli_skips_auto_update_notice_for_machine_output(monkeypatch, tmp_path: Path) -> None:
    import atlassian_cli.cli as cli_module

    monkeypatch.setattr(cli_module, "_stderr_is_interactive", lambda: True)

    def fail_check(current_version):
        raise AssertionError("machine output must not run automatic update checks")

    monkeypatch.setattr(cli_module, "check_for_update_notice", fail_check)

    result = runner.invoke(
        app,
        [
            "--output",
            "json",
            "init",
            "jira",
            "--config-file",
            str(tmp_path / "config.toml"),
            "--deployment",
            "server",
            "--url",
            "https://example.com",
            "--auth",
            "pat",
            "--token",
            "secret",
        ],
    )

    assert result.exit_code == 0
    assert "Wrote [jira]" in result.stdout
