import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.gh_compat.selectors import (
    RepositoryRef,
    ServerIdentity,
    parse_repository_selector,
)

RunGit = Callable[[list[str], Path], subprocess.CompletedProcess[str]]
ChooseRemote = Callable[[list[str]], str]


@dataclass(frozen=True)
class GitRepositorySnapshot:
    current_branch: str | None
    default_remote: str | None
    upstream_remote: str | None
    remotes: dict[str, str]


@dataclass(frozen=True)
class RepositoryResolution:
    repository: RepositoryRef
    current_branch: str | None


class GitRepositoryContext:
    def __init__(self, cwd: Path, *, run_git: RunGit | None = None) -> None:
        self.cwd = Path(cwd)
        self.run_git = run_git

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if self.run_git is not None:
            return self.run_git(args, self.cwd)
        return subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            check=False,
            capture_output=True,
            text=True,
        )

    def _read(self, args: list[str]) -> str | None:
        result = self._run(args)
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def read(self) -> GitRepositorySnapshot:
        remote_names = (self._read(["remote"]) or "").splitlines()
        remotes: dict[str, str] = {}
        for name in remote_names:
            url = self._read(["remote", "get-url", name])
            if url is not None:
                remotes[name] = url

        current_branch = self._read(["symbolic-ref", "--quiet", "--short", "HEAD"])
        upstream_remote = None
        if current_branch is not None:
            upstream_remote = self._read(
                [
                    "for-each-ref",
                    "--format=%(upstream:remotename)",
                    f"refs/heads/{current_branch}",
                ]
            )

        marked_remotes = [
            name
            for name in remotes
            if self._read(["config", "--get", f"remote.{name}.atlassian-resolved"]) == "base"
        ]
        default_remote = marked_remotes[0] if len(marked_remotes) == 1 else None

        return GitRepositorySnapshot(
            current_branch=current_branch,
            default_remote=default_remote,
            upstream_remote=upstream_remote,
            remotes=remotes,
        )


class RepositoryResolver:
    def __init__(
        self,
        server: ServerIdentity,
        git: GitRepositorySnapshot,
        *,
        env: Mapping[str, str] | None = None,
        can_prompt: bool = False,
        choose_remote: ChooseRemote | None = None,
    ) -> None:
        self.server = server
        self.git = git
        self.env = os.environ if env is None else env
        self.can_prompt = can_prompt
        self.choose_remote = choose_remote

    def _matching_remotes(self) -> dict[str, RepositoryRef]:
        matches: dict[str, RepositoryRef] = {}
        for name, url in self.git.remotes.items():
            try:
                matches[name] = parse_repository_selector(url, self.server)
            except ValidationError:
                continue
        return matches

    def resolve(
        self,
        *,
        explicit: str | None = None,
        embedded: RepositoryRef | None = None,
    ) -> RepositoryResolution:
        if embedded is not None:
            selected = embedded
        elif explicit is not None:
            selected = parse_repository_selector(explicit, self.server)
        elif self.env.get("ATLASSIAN_BITBUCKET_REPO"):
            selected = parse_repository_selector(self.env["ATLASSIAN_BITBUCKET_REPO"], self.server)
        else:
            matches = self._matching_remotes()
            selected = self._first_preferred_match(matches)
            if selected is None:
                selected = self._fallback_match(matches)
        return RepositoryResolution(selected, self.git.current_branch)

    def _first_preferred_match(self, matches: Mapping[str, RepositoryRef]) -> RepositoryRef | None:
        for name in (self.git.default_remote, self.git.upstream_remote, "origin"):
            if name is not None and name in matches:
                return matches[name]
        return None

    def _fallback_match(self, matches: Mapping[str, RepositoryRef]) -> RepositoryRef:
        names = list(matches)
        if len(names) == 1:
            return matches[names[0]]
        if not names:
            raise ValidationError("unable to determine a Bitbucket repository; use -R")
        if self.can_prompt and self.choose_remote is not None:
            chosen = self.choose_remote(names)
            if chosen in matches:
                return matches[chosen]
        raise ValidationError(f"multiple Bitbucket remotes match: {', '.join(names)}; use -R")
