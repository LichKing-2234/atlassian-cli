import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ATLASSIAN_ACCEPT_ENV_PATTERN = "ATLASSIAN_*"
DEFAULT_SSHD_CONFIG_PATH = Path("/etc/ssh/sshd_config")
DEFAULT_SSHD_CONFIG_DROP_IN_DIR = Path("/etc/ssh/sshd_config.d")
DEFAULT_SSHD_DROP_IN_FILE = "99-atlassian-cli-accept-env.conf"

ReloadRunner = Callable[[tuple[str, ...]], bool]


@dataclass(frozen=True)
class SshAcceptEnvSetupResult:
    status: str
    path: Path | None = None
    reloaded: bool = False
    reload_command: str | None = None
    error: str | None = None


def ensure_local_ssh_accept_env(
    *,
    pattern: str = ATLASSIAN_ACCEPT_ENV_PATTERN,
    sshd_config_path: Path = DEFAULT_SSHD_CONFIG_PATH,
    sshd_config_drop_in_dir: Path = DEFAULT_SSHD_CONFIG_DROP_IN_DIR,
    drop_in_filename: str = DEFAULT_SSHD_DROP_IN_FILE,
    reload: bool = True,
    reload_runner: ReloadRunner | None = None,
) -> SshAcceptEnvSetupResult:
    if not sshd_config_path.exists():
        return SshAcceptEnvSetupResult(status="unavailable")

    configured_path = _find_existing_accept_env(
        pattern,
        sshd_config_path=sshd_config_path,
        sshd_config_drop_in_dir=sshd_config_drop_in_dir,
    )
    if configured_path is not None:
        return SshAcceptEnvSetupResult(status="already_configured", path=configured_path)

    target_path = _target_accept_env_path(
        sshd_config_path=sshd_config_path,
        sshd_config_drop_in_dir=sshd_config_drop_in_dir,
        drop_in_filename=drop_in_filename,
    )

    try:
        _write_accept_env_pattern(target_path, pattern)
    except PermissionError:
        return SshAcceptEnvSetupResult(
            status="permission_denied",
            path=target_path,
            reload_command=_reload_command_hint(),
        )
    except OSError as exc:
        return SshAcceptEnvSetupResult(
            status="write_failed",
            path=target_path,
            reload_command=_reload_command_hint(),
            error=str(exc),
        )

    reloaded = False
    if reload:
        reloaded = _reload_sshd(reload_runner=reload_runner)

    return SshAcceptEnvSetupResult(
        status="updated",
        path=target_path,
        reloaded=reloaded,
        reload_command=None if reloaded else _reload_command_hint(),
    )


def _find_existing_accept_env(
    pattern: str,
    *,
    sshd_config_path: Path,
    sshd_config_drop_in_dir: Path,
) -> Path | None:
    paths = [sshd_config_path]
    if _uses_drop_in_dir(
        sshd_config_path=sshd_config_path, sshd_config_drop_in_dir=sshd_config_drop_in_dir
    ):
        paths.extend(sorted(sshd_config_drop_in_dir.glob("*.conf")))

    for path in paths:
        if not path.exists():
            continue
        if _file_has_accept_env(path, pattern):
            return path
    return None


def _target_accept_env_path(
    *,
    sshd_config_path: Path,
    sshd_config_drop_in_dir: Path,
    drop_in_filename: str,
) -> Path:
    if _uses_drop_in_dir(
        sshd_config_path=sshd_config_path, sshd_config_drop_in_dir=sshd_config_drop_in_dir
    ):
        return sshd_config_drop_in_dir / drop_in_filename
    return sshd_config_path


def _uses_drop_in_dir(*, sshd_config_path: Path, sshd_config_drop_in_dir: Path) -> bool:
    include_glob = f"{sshd_config_drop_in_dir}/*.conf"
    for line in sshd_config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith("Include "):
            continue
        if include_glob in stripped.split()[1:]:
            return True
    return False


def _file_has_accept_env(path: Path, pattern: str) -> bool:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        before_comment = stripped.split("#", 1)[0].strip()
        parts = before_comment.split()
        if parts and parts[0] == "AcceptEnv" and pattern in parts[1:]:
            return True
    return False


def _write_accept_env_pattern(path: Path, pattern: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"AcceptEnv {pattern}\n", encoding="utf-8")
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        before_comment, comment_sep, comment = line.partition("#")
        parts = before_comment.split()
        if not parts or parts[0] != "AcceptEnv":
            continue
        if pattern in parts[1:]:
            return
        updated = before_comment.rstrip() + f" {pattern}"
        if comment_sep:
            updated = f"{updated} {comment_sep}{comment}"
        lines[index] = updated
        break
    else:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append("# Allow atlassian-cli env forwarding over SSH")
        lines.append(f"AcceptEnv {pattern}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _reload_sshd(*, reload_runner: ReloadRunner | None) -> bool:
    runner = reload_runner or _run_reload_command
    for command in _reload_commands():
        if runner(command):
            return True
    return False


def _run_reload_command(command: tuple[str, ...]) -> bool:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def _reload_commands() -> tuple[tuple[str, ...], ...]:
    if platform.system() == "Darwin":
        return (("launchctl", "kickstart", "-k", "system/com.openssh.sshd"),)
    return (
        ("systemctl", "reload", "ssh"),
        ("systemctl", "reload", "sshd"),
        ("service", "ssh", "reload"),
        ("service", "sshd", "reload"),
    )


def _reload_command_hint() -> str:
    if platform.system() == "Darwin":
        return "sudo launchctl kickstart -k system/com.openssh.sshd"
    return "sudo systemctl reload ssh || sudo systemctl reload sshd"
