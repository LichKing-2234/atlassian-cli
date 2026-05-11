import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
INSTALL_PS1 = REPO_ROOT / "install.ps1"


def _write_release_fixture(
    tmp_path: Path,
    *,
    tag: str = "v0.1.0",
    target_os: str = "linux",
    target_arch: str = "amd64",
    checksum_mismatch: bool = False,
    symlink_payload: bool = False,
) -> tuple[Path, Path, str]:
    downloads_root = tmp_path / "downloads"
    release_dir = downloads_root / tag
    release_dir.mkdir(parents=True)

    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    binary_path = payload_dir / "atlassian"
    if symlink_payload:
        binary_path.symlink_to("/etc/passwd")
    else:
        binary_path.write_text("#!/bin/sh\necho fixture-atlassian\n")
        binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR)

    archive_name = f"atlassian-cli_0.1.0_{target_os}_{target_arch}.tar.gz"
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


def _write_bundle_release_fixture(
    tmp_path: Path,
    *,
    tag: str = "v0.1.0",
    target_os: str = "linux",
    target_arch: str = "amd64",
    unsafe_symlink: bool = False,
    hardlink_payload: bool = False,
) -> tuple[Path, Path, str]:
    downloads_root = tmp_path / "downloads"
    release_dir = downloads_root / tag
    release_dir.mkdir(parents=True)

    bundle_dir = tmp_path / "payload" / "atlassian"
    internal_dir = bundle_dir / "_internal"
    internal_dir.mkdir(parents=True)
    (internal_dir / "runtime-marker").write_text("fixture-runtime\n")
    (internal_dir / "runtime-link").symlink_to("runtime-marker")
    if unsafe_symlink:
        (internal_dir / "unsafe-link").symlink_to("/etc/passwd")
    binary_path = bundle_dir / "atlassian"
    binary_path.write_text("#!/bin/sh\necho fixture-bundle-atlassian\n")
    binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR)

    archive_name = f"atlassian-cli_0.1.0_{target_os}_{target_arch}.tar.gz"
    archive_path = release_dir / archive_name
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname="atlassian")
        if hardlink_payload:
            hardlink_info = tarfile.TarInfo("atlassian/_internal/runtime-hardlink")
            hardlink_info.type = tarfile.LNKTYPE
            hardlink_info.linkname = "atlassian/_internal/runtime-marker"
            tar.addfile(hardlink_info)

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
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


def test_install_script_installs_onedir_bundle_archive(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_bundle_release_fixture(tmp_path)
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
    installed_shim = install_dir / "atlassian"
    installed_bundle = install_dir / ".atlassian-cli" / "atlassian"
    assert installed_shim.exists()
    assert os.access(installed_shim, os.X_OK)
    assert (installed_bundle / "atlassian").exists()
    assert (installed_bundle / "_internal" / "runtime-marker").exists()
    assert (installed_bundle / "_internal" / "runtime-link").exists()

    run_result = subprocess.run(
        [str(installed_shim)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert run_result.stdout.strip() == "fixture-bundle-atlassian"


def test_install_script_installs_latest_darwin_amd64_bundle(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_bundle_release_fixture(
        tmp_path,
        target_os="darwin",
        target_arch="amd64",
    )
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
            "INSTALL_TEST_OS": "Darwin",
            "INSTALL_TEST_ARCH": "x86_64",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    installed_shim = install_dir / "atlassian"
    assert installed_shim.exists()
    assert os.access(installed_shim, os.X_OK)
    assert (install_dir / ".atlassian-cli" / "atlassian" / "atlassian").exists()


def test_install_powershell_script_supports_windows_amd64_zip_releases() -> None:
    script = INSTALL_PS1.read_text()

    assert '$RepoOwner = "LichKing-2234"' in script
    assert '$RepoName = "atlassian-cli"' in script
    assert "atlassian-cli_${ReleaseVersion}_windows_amd64.zip" in script
    assert "Invoke-RestMethod" in script
    assert "Invoke-WebRequest" in script
    assert "Get-FileHash" in script
    assert "Expand-Archive" in script
    assert "Assert-ZipLayout" in script
    assert "atlassian.cmd" in script


def test_install_powershell_script_uses_timeout_for_downloads() -> None:
    script = INSTALL_PS1.read_text()

    assert '$InstallRequestTimeoutSec = if ($env:INSTALL_CURL_MAX_TIME)' in script
    assert "Invoke-RestMethod -Uri $ReleaseApiUrl -Headers $Headers -TimeoutSec $InstallRequestTimeoutSec" in script
    assert "Invoke-WebRequest -Uri $Url -OutFile $Destination -TimeoutSec $InstallRequestTimeoutSec" in script


def test_readme_documents_powershell_installer_for_windows() -> None:
    readme = (REPO_ROOT / "README.md").read_text()

    assert "install.ps1" in readme
    assert (
        "irm https://raw.githubusercontent.com/LichKing-2234/atlassian-cli/main/install.ps1 | iex"
        in readme
    )


def test_install_script_rejects_bundle_symlink_outside_archive(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_bundle_release_fixture(
        tmp_path,
        unsafe_symlink=True,
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
    assert "unsafe symbolic link" in result.stderr.lower()


def test_install_script_rejects_bundle_hardlink_entries(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_bundle_release_fixture(
        tmp_path,
        hardlink_payload=True,
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
    assert "hard link" in result.stderr.lower()


def test_install_script_extracts_single_binary_archive_once(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_release_fixture(tmp_path)
    real_tar = shutil.which("tar")
    assert real_tar is not None
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    tar_log = tmp_path / "tar-calls.log"
    tar_wrapper = tools_dir / "tar"
    tar_wrapper.write_text(
        f"""#!/bin/sh
printf 'tar\\n' >> "${{TAR_CALL_LOG}}"
exec "{real_tar}" "$@"
"""
    )
    tar_wrapper.chmod(tar_wrapper.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(tmp_path / "bin"),
            "INSTALL_RELEASE_API_URL": latest_json.resolve().as_uri(),
            "INSTALL_RELEASE_DOWNLOAD_BASE": downloads_root.resolve().as_uri(),
            "INSTALL_TEST_OS": "Linux",
            "INSTALL_TEST_ARCH": "x86_64",
            "PATH": f"{tools_dir}{os.pathsep}{os.environ['PATH']}",
            "TAR_CALL_LOG": str(tar_log),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert tar_log.read_text().splitlines() == ["tar", "tar"]


def test_install_script_rejects_unsupported_platform(tmp_path: Path) -> None:
    result = subprocess.run(
        ["sh", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=os.environ
        | {
            "HOME": str(tmp_path / "home"),
            "INSTALL_DIR": str(tmp_path / "bin"),
            "INSTALL_VERSION": "v0.1.0",
            "INSTALL_TEST_OS": "Linux",
            "INSTALL_TEST_ARCH": "aarch64",
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


def test_install_script_rejects_symlink_payload(tmp_path: Path) -> None:
    latest_json, downloads_root, _ = _write_release_fixture(
        tmp_path,
        symlink_payload=True,
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
    assert "symbolic link" in result.stderr.lower()


def test_install_script_uses_curl_progress_bar_for_downloads() -> None:
    script = INSTALL_SCRIPT.read_text()

    assert "curl --fail --location --progress-bar" in script
    assert 'INSTALL_CURL_CONNECT_TIMEOUT="${INSTALL_CURL_CONNECT_TIMEOUT:-10}"' in script
    assert 'INSTALL_CURL_MAX_TIME="${INSTALL_CURL_MAX_TIME:-120}"' in script
    assert '--connect-timeout "${INSTALL_CURL_CONNECT_TIMEOUT}"' in script
    assert '--max-time "${INSTALL_CURL_MAX_TIME}"' in script
