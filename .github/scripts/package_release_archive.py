#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tarfile
import zipfile
from pathlib import Path


def archive_name(version: str, target_os: str, target_arch: str, archive_format: str) -> str:
    extension = "zip" if archive_format == "zip" else "tar.gz"
    return f"atlassian-cli_{version}_{target_os}_{target_arch}.{extension}"


def create_tar_gz(bundle_dir: Path, archive_path: Path) -> None:
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname="atlassian")


def create_zip(bundle_dir: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(bundle_dir.rglob("*")):
            zip_file.write(path, path.relative_to(bundle_dir.parent))


def write_github_output(name: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as output:
        output.write(f"archive_name={name}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Package a release bundle archive.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--target-os", required=True)
    parser.add_argument("--target-arch", required=True)
    parser.add_argument("--archive-format", choices=("tar.gz", "zip"), required=True)
    args = parser.parse_args()

    bundle_dir = Path("dist") / "atlassian"
    if not bundle_dir.is_dir():
        raise SystemExit("dist/atlassian does not exist")

    name = archive_name(args.version, args.target_os, args.target_arch, args.archive_format)
    archive_path = Path(name)
    if args.archive_format == "zip":
        create_zip(bundle_dir, archive_path)
    else:
        create_tar_gz(bundle_dir, archive_path)

    write_github_output(name)
    print(name)


if __name__ == "__main__":
    main()
