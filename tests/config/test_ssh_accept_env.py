from pathlib import Path

from atlassian_cli.config.ssh_accept_env import ensure_local_ssh_accept_env


def test_ensure_local_ssh_accept_env_updates_main_config(tmp_path: Path) -> None:
    sshd_config = tmp_path / "sshd_config"
    sshd_config.write_text("AcceptEnv LANG LC_*\n", encoding="utf-8")

    result = ensure_local_ssh_accept_env(
        sshd_config_path=sshd_config,
        sshd_config_drop_in_dir=tmp_path / "sshd_config.d",
        reload=False,
    )

    assert result.status == "updated"
    assert result.path == sshd_config
    assert result.reloaded is False
    assert "AcceptEnv LANG LC_* ATLASSIAN_*\n" == sshd_config.read_text(encoding="utf-8")


def test_ensure_local_ssh_accept_env_uses_drop_in_when_available(tmp_path: Path) -> None:
    drop_in_dir = tmp_path / "sshd_config.d"
    sshd_config = tmp_path / "sshd_config"
    sshd_config.write_text(f"Include {drop_in_dir}/*.conf\n", encoding="utf-8")

    result = ensure_local_ssh_accept_env(
        sshd_config_path=sshd_config,
        sshd_config_drop_in_dir=drop_in_dir,
        reload=False,
    )

    target = drop_in_dir / "99-atlassian-cli-accept-env.conf"
    assert result.status == "updated"
    assert result.path == target
    assert target.read_text(encoding="utf-8") == "AcceptEnv ATLASSIAN_*\n"


def test_ensure_local_ssh_accept_env_reports_existing_drop_in_config(tmp_path: Path) -> None:
    drop_in_dir = tmp_path / "sshd_config.d"
    drop_in_dir.mkdir()
    sshd_config = tmp_path / "sshd_config"
    sshd_config.write_text(f"Include {drop_in_dir}/*.conf\n", encoding="utf-8")
    configured = drop_in_dir / "custom.conf"
    configured.write_text("AcceptEnv LANG LC_* ATLASSIAN_*\n", encoding="utf-8")

    result = ensure_local_ssh_accept_env(
        sshd_config_path=sshd_config,
        sshd_config_drop_in_dir=drop_in_dir,
        reload=False,
    )

    assert result.status == "already_configured"
    assert result.path == configured
