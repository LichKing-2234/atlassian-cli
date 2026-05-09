#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def release_version(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def merged_tags(tag: str) -> list[str]:
    output = run_git(["tag", "--sort=version:refname", "--merged", tag])
    return [line.strip() for line in output.splitlines() if line.strip()]


def previous_tag(tag: str) -> str | None:
    tags = merged_tags(tag)
    if tag not in tags:
        return None
    index = tags.index(tag)
    return tags[index - 1] if index > 0 else None


def change_subjects(tag: str) -> list[str]:
    previous = previous_tag(tag)
    revision = f"{previous}..{tag}" if previous else tag
    output = run_git(["log", "--first-parent", "--pretty=format:%s", revision])
    subjects = [line.strip() for line in output.splitlines() if line.strip()]
    return subjects or ["No code changes in this release."]


def build_release_notes(tag: str) -> str:
    version = release_version(tag)
    lines = [
        "## Changes",
        "",
        *[f"- {subject}" for subject in change_subjects(tag)],
        "",
        "## Assets",
        "",
        f"- `atlassian-cli_{version}_linux_amd64.tar.gz`",
        f"- `atlassian-cli_{version}_darwin_arm64.tar.gz`",
        f"- `atlassian-cli_{version}_darwin_amd64.tar.gz`",
        f"- `atlassian-cli_{version}_windows_amd64.zip`",
        "- `checksums.txt`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate GitHub release notes.")
    parser.add_argument("tag", help="Release tag, for example v0.1.0")
    parser.add_argument("output", type=Path, help="Markdown file to write")
    args = parser.parse_args()

    args.output.write_text(build_release_notes(args.tag))


if __name__ == "__main__":
    main()
