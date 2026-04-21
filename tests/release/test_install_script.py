import hashlib
import json
import os
import stat
import subprocess
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"


def _write_release_fixture(
    tmp_path: Path,
    *,
    tag: str = "v0.1.0",
    checksum_mismatch: bool = False,
) -> tuple[Path, Path, str]:
    downloads_root = tmp_path / "downloads"
    release_dir = downloads_root / tag
    release_dir.mkdir(parents=True)

    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    binary_path = payload_dir / "atlassian"
    binary_path.write_text("#!/bin/sh\necho fixture-atlassian\n")
    binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR)

    archive_name = "atlassian-cli_0.1.0_linux_amd64.tar.gz"
    archive_path = release_dir / archive_name
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(binary_path, arcname="atlassian")

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if checksum_mismatch:
        digest = "0" * 64
    (release_dir / "checksums.txt").write_text(f"{digest}  {archive_name}\n")

    latest_json = tmp_path / "latest.json"
    latest_json.write_text(json.dumps({"tag_name": tag}))
    return latest_json, downloads_root, archive_name


def test_install_script_installs_latest_linux_binary(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_release_fixture(tmp_path)
    install_dir = tmp_path / "bin"

    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(install_dir),
            "INSTALL_RELEASE_API_URL": latest_json.resolve().as_uri(),
            "INSTALL_RELEASE_DOWNLOAD_BASE": downloads_root.resolve().as_uri(),
            "INSTALL_TEST_OS": "Linux",
            "INSTALL_TEST_ARCH": "x86_64",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    installed_binary = install_dir / "atlassian"
    assert installed_binary.exists()
    assert os.access(installed_binary, os.X_OK)

    run_result = subprocess.run(
        [str(installed_binary)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert run_result.stdout.strip() == "fixture-atlassian"


def test_install_script_rejects_unsupported_platform(tmp_path: Path) -> None:
    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(tmp_path / "bin"),
            "INSTALL_VERSION": "v0.1.0",
            "INSTALL_TEST_OS": "Darwin",
            "INSTALL_TEST_ARCH": "x86_64",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "unsupported platform" in result.stderr.lower()


def test_install_script_fails_on_checksum_mismatch(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_release_fixture(
        tmp_path,
        checksum_mismatch=True,
    )

    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(tmp_path / "bin"),
            "INSTALL_VERSION": "v0.1.0",
            "INSTALL_RELEASE_API_URL": latest_json.resolve().as_uri(),
            "INSTALL_RELEASE_DOWNLOAD_BASE": downloads_root.resolve().as_uri(),
            "INSTALL_TEST_OS": "Linux",
            "INSTALL_TEST_ARCH": "x86_64",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr.lower()
