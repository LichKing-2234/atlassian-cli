import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import yaml


def test_release_workflow_builds_expected_platform_matrix() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    matrix = workflow["jobs"]["release"]["strategy"]["matrix"]["include"]

    targets = {
        (
            entry["runner"],
            entry["target_os"],
            entry["target_arch"],
            entry["archive_format"],
        )
        for entry in matrix
    }

    assert targets == {
        ("ubuntu-latest", "linux", "amd64", "tar.gz"),
        ("macos-latest", "darwin", "arm64", "tar.gz"),
        ("macos-15-intel", "darwin", "amd64", "tar.gz"),
        ("windows-latest", "windows", "amd64", "zip"),
    }


def test_release_workflow_uses_bash_for_cross_platform_release_steps() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    release = workflow["jobs"]["release"]

    assert release["defaults"]["run"]["shell"] == "bash"


def test_release_workflow_builds_linux_binary_in_older_glibc_container() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]

    linux_build = next(step for step in steps if step["name"] == "Build Linux binary")

    assert linux_build["if"] == "${{ matrix.target_os == 'linux' }}"
    assert "docker run --rm" in linux_build["run"]
    assert "--platform linux/amd64" in linux_build["run"]
    assert "python:3.12-bullseye" in linux_build["run"]
    assert "/workspace/.github/scripts/build-linux-compatible.sh" in linux_build["run"]


def test_release_workflow_uses_host_python_only_for_non_linux_binaries() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]

    host_python_steps = [
        step
        for step in steps
        if step["name"] in {"Set up Python", "Install dependencies", "Build native binary"}
    ]

    assert host_python_steps
    assert all(step["if"] == "${{ matrix.target_os != 'linux' }}" for step in host_python_steps)


def test_release_workflow_invokes_pyinstaller_through_python_module() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]

    build = next(step for step in steps if step["name"] == "Build native binary")

    assert "python -m PyInstaller atlassian.spec --clean --noconfirm" in build["run"]


def test_release_workflow_packages_release_archives_with_shared_script() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]

    package = next(step for step in steps if step["name"] == "Package archive")

    assert package["id"] == "package"
    assert "python .github/scripts/package_release_archive.py" in package["run"]
    assert '--archive-format "${{ matrix.archive_format }}"' in package["run"]


def test_release_workflow_builds_checksums_after_all_platform_archives() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())

    checksums = workflow["jobs"]["checksums"]
    build_step = next(
        step for step in checksums["steps"] if step["name"] == "Build release checksums"
    )
    upload_step = next(
        step for step in checksums["steps"] if step.get("uses") == "softprops/action-gh-release@v2"
    )

    assert checksums["needs"] == ["prepare", "release"]
    assert checksums["runs-on"] == "ubuntu-latest"
    assert "atlassian-cli_*.tar.gz" in build_step["run"]
    assert "atlassian-cli_*.zip" in build_step["run"]
    assert "sha256sum atlassian-cli_* > checksums.txt" in build_step["run"]
    assert upload_step["with"]["files"] == "release-assets/checksums.txt"


def test_linux_build_script_uses_python312_and_smoke_tests_binary() -> None:
    script = Path(".github/scripts/build-linux-compatible.sh").read_text()

    assert "/usr/local/bin/python" in script
    assert "pyinstaller atlassian.spec --clean --noconfirm" in script
    assert "./dist/atlassian/atlassian --help >/dev/null" in script
    assert "GLIBC_2\\.(3[8-9]|[4-9][0-9])" in script


def test_release_workflow_publishes_generated_release_notes() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["release"]["steps"]

    checkout = next(step for step in steps if step["name"] == "Check out repository")
    release_notes = next(step for step in steps if step["name"] == "Generate release notes")
    upload_steps = [step for step in steps if step.get("uses") == "softprops/action-gh-release@v2"]

    assert checkout["with"]["fetch-depth"] == 0
    assert "python .github/scripts/generate_release_notes.py" in release_notes["run"]
    assert upload_steps
    assert all(step["with"]["body_path"] == "release-notes.md" for step in upload_steps)


def test_release_workflow_notifies_wecom_after_publish() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release.yml").read_text())

    notify = workflow["jobs"]["notify"]
    step = next(step for step in notify["steps"] if step["name"] == "Notify WeCom release")

    assert notify["needs"] == ["prepare", "checksums"]
    assert "needs.checksums.result == 'success'" in notify["if"]
    assert step["env"]["GH_TOKEN"] == "${{ secrets.RELEASE_TOKEN || github.token }}"
    assert step["env"]["WECHAT_WEBHOOK_URL"] == "${{ secrets.WECHAT_WEBHOOK_URL }}"
    assert "WECHAT_WEBHOOK_URL secret is required" in step["run"]
    assert "gh release view" in step["run"]
    assert "release-notes.txt" in step["run"]
    assert "mentioned_list" not in step["run"]
    assert "@all" not in step["run"]
    assert "curl -fsS" in step["run"]


def test_package_release_archive_script_creates_tar_gz_bundle(tmp_path: Path) -> None:
    script = Path(".github/scripts/package_release_archive.py").resolve()
    bundle = tmp_path / "dist" / "atlassian"
    bundle.mkdir(parents=True)
    executable = bundle / "atlassian"
    executable.write_text("#!/bin/sh\necho fixture\n")
    executable.chmod(0o755)
    github_output = tmp_path / "github-output.txt"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--version",
            "0.1.0",
            "--target-os",
            "linux",
            "--target-arch",
            "amd64",
            "--archive-format",
            "tar.gz",
        ],
        cwd=tmp_path,
        env={"GITHUB_OUTPUT": str(github_output)},
        check=True,
        capture_output=True,
        text=True,
    )

    archive = tmp_path / "atlassian-cli_0.1.0_linux_amd64.tar.gz"
    assert archive.exists()
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        member = tar.getmember("atlassian/atlassian")
    assert "atlassian/atlassian" in names
    assert member.mode & 0o111
    assert github_output.read_text() == "archive_name=atlassian-cli_0.1.0_linux_amd64.tar.gz\n"


def test_package_release_archive_script_creates_windows_zip_bundle(tmp_path: Path) -> None:
    script = Path(".github/scripts/package_release_archive.py").resolve()
    bundle = tmp_path / "dist" / "atlassian"
    bundle.mkdir(parents=True)
    (bundle / "atlassian.exe").write_text("fixture exe")
    github_output = tmp_path / "github-output.txt"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--version",
            "0.1.0",
            "--target-os",
            "windows",
            "--target-arch",
            "amd64",
            "--archive-format",
            "zip",
        ],
        cwd=tmp_path,
        env={"GITHUB_OUTPUT": str(github_output)},
        check=True,
        capture_output=True,
        text=True,
    )

    archive = tmp_path / "atlassian-cli_0.1.0_windows_amd64.zip"
    assert archive.exists()
    with zipfile.ZipFile(archive) as zip_file:
        names = zip_file.namelist()
    assert "atlassian/atlassian.exe" in names
    assert github_output.read_text() == "archive_name=atlassian-cli_0.1.0_windows_amd64.zip\n"


def test_generate_release_notes_script_outputs_changes_and_assets(tmp_path) -> None:
    script = Path(".github/scripts/generate_release_notes.py").resolve()
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Example Author"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "example@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    (repo / "README.md").write_text("initial\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: initial release"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "tag", "v0.1.0"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("initial\nupdate\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "fix: update release behavior"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "tag", "v0.1.1"], cwd=repo, check=True, capture_output=True)

    output = repo / "release-notes.md"
    subprocess.run(
        [sys.executable, str(script), "v0.1.1", str(output)],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    notes = output.read_text()
    assert "## Changes" in notes
    assert "- fix: update release behavior" in notes
    assert "feat: initial release" not in notes
    assert "## Assets" in notes
    assert "`atlassian-cli_0.1.1_linux_amd64.tar.gz`" in notes
    assert "`atlassian-cli_0.1.1_darwin_arm64.tar.gz`" in notes
    assert "`atlassian-cli_0.1.1_darwin_amd64.tar.gz`" in notes
    assert "`atlassian-cli_0.1.1_windows_amd64.zip`" in notes
    assert "`checksums.txt`" in notes
