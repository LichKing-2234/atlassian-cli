import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import certifi

REPO_OWNER = "LichKing-2234"
REPO_NAME = "atlassian-cli"
LATEST_RELEASE_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
INSTALL_SCRIPT_URL_TEMPLATE = (
    f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{{tag}}/install.sh"
)
REQUEST_TIMEOUT_SECONDS = 10


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    version: str
    url: str | None = None


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest: ReleaseInfo
    update_available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version,
            "latest_version": self.latest.version,
            "latest_tag": self.latest.tag,
            "update_available": self.update_available,
            "release_url": self.latest.url,
        }


@dataclass(frozen=True)
class InstallResult:
    version: str
    install_dir: Path
    updated: bool
    message: str
    installer_stdout: str = ""
    installer_stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "install_dir": str(self.install_dir),
            "updated": self.updated,
            "message": self.message,
            "installer_stdout": self.installer_stdout,
            "installer_stderr": self.installer_stderr,
        }


def normalize_tag(version: str) -> str:
    value = version.strip()
    if not value:
        raise UpdateError("version must not be empty")
    return value if value.startswith("v") else f"v{value}"


def normalize_version(version: str) -> str:
    return normalize_tag(version)[1:]


def _version_parts(version: str) -> tuple[tuple[int, int, int], tuple[tuple[int, int | str], ...]]:
    normalized = normalize_version(version)
    core, _, suffix = normalized.partition("-")
    numbers = core.split(".")
    if len(numbers) != 3:
        raise UpdateError(f"unsupported version format: {version}")
    try:
        parsed_core = tuple(int(part) for part in numbers)
    except ValueError as exc:
        raise UpdateError(f"unsupported version format: {version}") from exc

    suffix_parts: list[tuple[int, int | str]] = []
    for part in suffix.replace("-", ".").split("."):
        if not part:
            continue
        suffix_parts.append((0, int(part)) if part.isdigit() else (1, part))
    return parsed_core, tuple(suffix_parts)


def compare_versions(left: str, right: str) -> int:
    left_core, left_suffix = _version_parts(left)
    right_core, right_suffix = _version_parts(right)
    if left_core != right_core:
        return 1 if left_core > right_core else -1
    if left_suffix == right_suffix:
        return 0
    if not left_suffix:
        return 1
    if not right_suffix:
        return -1
    return 1 if left_suffix > right_suffix else -1


def is_newer_version(candidate: str, current: str) -> bool:
    return compare_versions(candidate, current) > 0


def _https_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def fetch_latest_release(
    *,
    api_url: str = LATEST_RELEASE_API_URL,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> ReleaseInfo:
    try:
        with urlopen(api_url, timeout=timeout, context=_https_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise UpdateError(f"failed to fetch latest release: {exc}") from exc

    if not isinstance(payload, dict):
        raise UpdateError("failed to parse latest release metadata")

    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag.strip():
        raise UpdateError("failed to parse latest release tag")
    html_url = payload.get("html_url")
    return ReleaseInfo(
        tag=normalize_tag(tag),
        version=normalize_version(tag),
        url=html_url if isinstance(html_url, str) else None,
    )


def get_update_info(current_version: str) -> UpdateInfo:
    latest = fetch_latest_release()
    return UpdateInfo(
        current_version=current_version,
        latest=latest,
        update_available=is_newer_version(latest.version, current_version),
    )


def default_install_dir(
    *,
    environ: dict[str, str] | None = None,
    executable: str | None = None,
    frozen: bool | None = None,
    home: Path | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    for name in ("ATLASSIAN_INSTALL_DIR", "INSTALL_DIR"):
        value = env.get(name)
        if value:
            return Path(value).expanduser()

    executable_path = Path(executable or sys.executable).resolve()
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen

    bundle_parts = executable_path.parts
    if len(bundle_parts) >= 4 and bundle_parts[-3:] == (".atlassian-cli", "atlassian", "atlassian"):
        return Path(*bundle_parts[:-3])

    if is_frozen:
        launcher = shutil.which("atlassian")
        if launcher:
            return Path(launcher).resolve().parent
        return executable_path.parent

    return (home or Path.home()) / ".local" / "bin"


def _download_install_script(
    *,
    script_url: str,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> str:
    try:
        with urlopen(script_url, timeout=timeout, context=_https_context()) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
        raise UpdateError(f"failed to download install script: {exc}") from exc


def install_script_url_for_tag(tag: str) -> str:
    return INSTALL_SCRIPT_URL_TEMPLATE.format(tag=normalize_tag(tag))


def run_install_script(
    *,
    version: str,
    install_dir: Path,
    script_url: str | None = None,
    env: dict[str, str] | None = None,
) -> InstallResult:
    tag = normalize_tag(version)
    script = _download_install_script(script_url=script_url or install_script_url_for_tag(tag))
    run_env = dict(os.environ)
    if env is not None:
        run_env.update(env)
    run_env["INSTALL_VERSION"] = tag
    run_env["INSTALL_DIR"] = str(install_dir.expanduser())

    with tempfile.TemporaryDirectory(prefix="atlassian-cli-update-") as tmp_dir:
        script_path = Path(tmp_dir) / "install.sh"
        script_path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            ["sh", str(script_path)],
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        detail = stderr or stdout or f"installer exited with status {result.returncode}"
        raise UpdateError(detail)

    return InstallResult(
        version=tag,
        install_dir=install_dir.expanduser(),
        updated=True,
        message=stdout or f"installed {tag} to {install_dir.expanduser()}/atlassian",
        installer_stdout=stdout,
        installer_stderr=stderr,
    )


def install_update(
    *,
    current_version: str,
    version: str | None = None,
    install_dir: Path | None = None,
    force: bool = False,
) -> InstallResult:
    destination = install_dir.expanduser() if install_dir is not None else default_install_dir()
    if version is not None:
        return run_install_script(version=version, install_dir=destination)

    info = get_update_info(current_version)
    if not info.update_available and not force:
        return InstallResult(
            version=info.latest.tag,
            install_dir=destination,
            updated=False,
            message=f"atlassian-cli {current_version} is up to date",
        )
    return run_install_script(version=info.latest.tag, install_dir=destination)
