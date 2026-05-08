from pathlib import Path

import yaml


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


def test_linux_build_script_uses_python312_and_smoke_tests_binary() -> None:
    script = Path(".github/scripts/build-linux-compatible.sh").read_text()

    assert "/usr/local/bin/python" in script
    assert "pyinstaller atlassian.spec --clean --noconfirm" in script
    assert "./dist/atlassian/atlassian --help >/dev/null" in script
    assert "GLIBC_2\\.(3[8-9]|[4-9][0-9])" in script
