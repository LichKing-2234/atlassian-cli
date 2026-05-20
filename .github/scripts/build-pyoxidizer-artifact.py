#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = REPO_ROOT / ".pyoxidizer-build"
DIST_ROOT = REPO_ROOT / "dist"
PYOXIDIZER_VERSION = "0.24.0"
PYOXIDIZER_PYTHON = "3.10"
RUST_TOOLCHAIN = {
    ("linux", "amd64"): "1.84.1-x86_64-unknown-linux-gnu",
    ("darwin", "arm64"): "1.84.1-aarch64-apple-darwin",
    ("darwin", "amd64"): "1.84.1-x86_64-apple-darwin",
    ("windows", "amd64"): "1.84.1-x86_64-pc-windows-msvc",
}
TARGET_TRIPLE = {
    ("linux", "amd64"): "x86_64-unknown-linux-gnu",
    ("darwin", "arm64"): "aarch64-apple-darwin",
    ("darwin", "amd64"): "x86_64-apple-darwin",
    ("windows", "amd64"): "x86_64-pc-windows-msvc",
}


def venv_bin(venv_dir: Path, name: str) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return venv_dir / scripts_dir / f"{name}{suffix}"


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
    )


def read_project_dependencies() -> list[str]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(pyproject["project"]["dependencies"])


def ensure_venv(path: Path, *, python_spec: str) -> Path:
    if path.exists():
        shutil.rmtree(path)
    run(["uv", "venv", "-p", python_spec, str(path)])
    return venv_bin(path, "python")


def ensure_tool_venv(path: Path) -> Path:
    python = ensure_venv(path, python_spec=PYOXIDIZER_PYTHON)
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            f"pyoxidizer=={PYOXIDIZER_VERSION}",
            "tomli>=2.0.1",
        ]
    )
    return venv_bin(path, "pyoxidizer")


def ensure_runtime_venv(path: Path) -> Path:
    python = ensure_venv(path, python_spec=PYOXIDIZER_PYTHON)
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            *read_project_dependencies(),
            "tomli>=2.0.1",
        ]
    )
    return path


def smoke_executable(bundle_dir: Path, *, target_os: str) -> Path:
    executable_name = "atlassian.exe" if target_os == "windows" else "atlassian"
    return bundle_dir / executable_name


def command_output(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=REPO_ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a PyOxidizer standalone bundle.")
    parser.add_argument("--target-os", required=True, choices={"linux", "darwin", "windows"})
    parser.add_argument("--target-arch", required=True, choices={"amd64", "arm64"})
    parser.add_argument("--version", required=True)
    parser.add_argument("--archive-format", required=True, choices={"tar.gz", "zip"})
    args = parser.parse_args()

    target_key = (args.target_os, args.target_arch)
    target_triple = TARGET_TRIPLE[target_key]
    build_scope = BUILD_ROOT / f"{args.target_os}-{args.target_arch}"
    tool_venv = build_scope / "tool-venv"
    runtime_venv = build_scope / "runtime-venv"
    pyoxidizer = ensure_tool_venv(tool_venv)
    runtime_path = ensure_runtime_venv(runtime_venv)

    dist_bundle = DIST_ROOT / "atlassian"
    build_output = REPO_ROOT / "build" / target_triple
    if dist_bundle.exists():
        shutil.rmtree(dist_bundle)
    if build_output.exists():
        shutil.rmtree(build_output)

    env = os.environ.copy()
    env.setdefault("CARGO_REGISTRIES_CRATES_IO_PROTOCOL", "sparse")
    env.setdefault("RUSTUP_TOOLCHAIN", RUST_TOOLCHAIN[target_key])
    if args.target_os == "darwin":
        env.setdefault("SDKROOT", command_output(["xcrun", "--sdk", "macosx", "--show-sdk-path"]))
        env.setdefault("DEVELOPER_DIR", command_output(["xcode-select", "--print-path"]))

    run(
        [
            str(pyoxidizer),
            "--system-rust",
            "build",
            "--release",
            "--path",
            str(REPO_ROOT),
            "--target-triple",
            target_triple,
            "--var",
            "RUNTIME_VENV",
            str(runtime_path),
            "--var",
            "SOURCE_ROOT",
            str(REPO_ROOT / "src"),
            "--var",
            "APP_VERSION",
            args.version,
        ],
        env=env,
    )

    install_dir = build_output / "release" / "install"
    shutil.copytree(install_dir, dist_bundle)
    executable = smoke_executable(dist_bundle, target_os=args.target_os)
    subprocess.run([str(executable), "--version"], cwd=REPO_ROOT, check=True, text=True)


if __name__ == "__main__":
    main()
