import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from atlassian_cli.core.errors import ValidationError
from atlassian_cli.products.bitbucket.gh_compat.repository_context import (
    GitRepositoryContext,
    GitRepositorySnapshot,
    RepositoryResolver,
)
from atlassian_cli.products.bitbucket.gh_compat.selectors import RepositoryRef, ServerIdentity

SERVER = ServerIdentity.from_url("https://bitbucket.example.com")


def snapshot() -> GitRepositorySnapshot:
    return GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote="upstream",
        upstream_remote="origin",
        remotes={
            "origin": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
            "upstream": "ssh://git@bitbucket.example.com:7999/~example-user/example-repo.git",
        },
    )


def completed(
    args: list[str],
    *,
    stdout: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")


def fake_git(
    responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]],
) -> tuple[
    Callable[[list[str], Path], subprocess.CompletedProcess[str]],
    list[tuple[list[str], Path]],
]:
    calls: list[tuple[list[str], Path]] = []

    def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((args, cwd))
        return responses.get(tuple(args), completed(args, returncode=1))

    return run, calls


def test_embedded_url_repo_beats_explicit_environment_and_git() -> None:
    resolver = RepositoryResolver(
        SERVER,
        snapshot(),
        env={"ATLASSIAN_BITBUCKET_REPO": "~example-user/example-repo"},
    )
    embedded = RepositoryRef(SERVER, "DEMO", "example-repo")
    assert (
        resolver.resolve(
            explicit="~example-user/example-repo",
            embedded=embedded,
        ).repository
        == embedded
    )


def test_explicit_beats_environment_and_git() -> None:
    resolver = RepositoryResolver(
        SERVER,
        snapshot(),
        env={"ATLASSIAN_BITBUCKET_REPO": "~example-user/example-repo"},
    )
    assert resolver.resolve(explicit="DEMO/example-repo").repository == RepositoryRef(
        SERVER, "DEMO", "example-repo"
    )


def test_environment_beats_git() -> None:
    resolver = RepositoryResolver(
        SERVER,
        snapshot(),
        env={"ATLASSIAN_BITBUCKET_REPO": "DEMO/example-repo"},
    )
    assert resolver.resolve().repository == RepositoryRef(SERVER, "DEMO", "example-repo")


def test_invalid_environment_selector_is_not_hidden_by_git() -> None:
    resolver = RepositoryResolver(
        SERVER,
        snapshot(),
        env={"ATLASSIAN_BITBUCKET_REPO": "not-a-repository"},
    )
    with pytest.raises(ValidationError) as exc_info:
        resolver.resolve()
    assert str(exc_info.value) == "repository must use PROJECT/REPOSITORY syntax"


def test_default_remote_beats_branch_upstream_and_origin() -> None:
    result = RepositoryResolver(SERVER, snapshot(), env={}).resolve()
    assert result.repository == RepositoryRef(SERVER, "~example-user", "example-repo")


def test_branch_upstream_beats_origin() -> None:
    git = snapshot()
    git = GitRepositorySnapshot(
        current_branch=git.current_branch,
        default_remote=None,
        upstream_remote="upstream",
        remotes=git.remotes,
    )
    result = RepositoryResolver(SERVER, git, env={}).resolve()
    assert result.repository == RepositoryRef(SERVER, "~example-user", "example-repo")


def test_foreign_host_origin_is_ignored() -> None:
    git = GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote=None,
        upstream_remote=None,
        remotes={"origin": "https://foreign.example.com/scm/DEMO/example-repo.git"},
    )
    with pytest.raises(ValidationError) as exc_info:
        RepositoryResolver(SERVER, git, env={}).resolve()
    assert str(exc_info.value) == "unable to determine a Bitbucket repository; use -R"


def test_single_fallback_remote_is_selected() -> None:
    git = GitRepositorySnapshot(
        current_branch=None,
        default_remote=None,
        upstream_remote=None,
        remotes={
            "mirror": "https://foreign.example.com/scm/DEMO/example-repo.git",
            "work": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
        },
    )
    result = RepositoryResolver(SERVER, git, env={}).resolve()
    assert result.repository == RepositoryRef(SERVER, "DEMO", "example-repo")
    assert result.current_branch is None


def test_non_tty_remote_ambiguity_lists_names() -> None:
    ambiguous = GitRepositorySnapshot(
        current_branch=None,
        default_remote=None,
        upstream_remote=None,
        remotes={
            "one": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
            "two": "https://bitbucket.example.com/scm/~example-user/example-repo.git",
        },
    )
    with pytest.raises(ValidationError) as exc_info:
        RepositoryResolver(SERVER, ambiguous, env={}, can_prompt=False).resolve()
    assert str(exc_info.value) == "multiple Bitbucket remotes match: one, two; use -R"


def test_tty_ambiguity_uses_injected_chooser() -> None:
    ambiguous = GitRepositorySnapshot(
        current_branch="feature/DEMO-1234/example-change",
        default_remote=None,
        upstream_remote=None,
        remotes={
            "one": "https://bitbucket.example.com/scm/DEMO/example-repo.git",
            "two": "https://bitbucket.example.com/scm/~example-user/example-repo.git",
        },
    )
    resolver = RepositoryResolver(
        SERVER,
        ambiguous,
        env={},
        can_prompt=True,
        choose_remote=lambda names: names[1],
    )
    assert resolver.resolve().repository.project_key == "~example-user"


def test_git_reader_runs_only_read_commands(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "remote",
            "add",
            "origin",
            "https://bitbucket.example.com/scm/DEMO/example-repo.git",
        ],
        check=True,
    )
    result = GitRepositoryContext(tmp_path).read()
    assert result.remotes == {"origin": "https://bitbucket.example.com/scm/DEMO/example-repo.git"}
    assert result.default_remote is None


def test_git_reader_captures_only_approved_read_commands(tmp_path: Path) -> None:
    branch = "feature/DEMO-1234/example-change"
    responses = {
        ("remote",): completed(["remote"], stdout="origin\nupstream\n"),
        ("remote", "get-url", "origin"): completed(
            ["remote", "get-url", "origin"],
            stdout="https://bitbucket.example.com/scm/DEMO/example-repo.git\n",
        ),
        ("remote", "get-url", "upstream"): completed(
            ["remote", "get-url", "upstream"],
            stdout="ssh://git@bitbucket.example.com:7999/~example-user/example-repo.git\n",
        ),
        ("symbolic-ref", "--quiet", "--short", "HEAD"): completed(
            ["symbolic-ref", "--quiet", "--short", "HEAD"], stdout=f"{branch}\n"
        ),
        (
            "for-each-ref",
            "--format=%(upstream:remotename)",
            f"refs/heads/{branch}",
        ): completed(
            [
                "for-each-ref",
                "--format=%(upstream:remotename)",
                f"refs/heads/{branch}",
            ],
            stdout="origin\n",
        ),
        ("config", "--get", "remote.origin.atlassian-resolved"): completed(
            ["config", "--get", "remote.origin.atlassian-resolved"]
        ),
        ("config", "--get", "remote.upstream.atlassian-resolved"): completed(
            ["config", "--get", "remote.upstream.atlassian-resolved"], stdout="base\n"
        ),
    }
    run_git, calls = fake_git(responses)

    result = GitRepositoryContext(tmp_path, run_git=run_git).read()

    assert result == snapshot()
    assert calls
    assert all(cwd == tmp_path for _, cwd in calls)
    assert all(
        isinstance(args, list) and all(isinstance(arg, str) for arg in args) for args, _ in calls
    )
    assert {args[0] for args, _ in calls} <= {
        "remote",
        "symbolic-ref",
        "for-each-ref",
        "config",
    }
    assert all("clone" not in args and "fetch" not in args for args, _ in calls)
    assert all("password" not in " ".join(args).lower() for args, _ in calls)
    assert all(args[:2] == ["config", "--get"] for args, _ in calls if args[0] == "config")


def test_multiple_default_markers_do_not_select_a_default(tmp_path: Path) -> None:
    responses = {
        ("remote",): completed(["remote"], stdout="one\ntwo\n"),
        ("remote", "get-url", "one"): completed(
            ["remote", "get-url", "one"],
            stdout="https://bitbucket.example.com/scm/DEMO/example-repo.git\n",
        ),
        ("remote", "get-url", "two"): completed(
            ["remote", "get-url", "two"],
            stdout="https://bitbucket.example.com/scm/~example-user/example-repo.git\n",
        ),
        ("symbolic-ref", "--quiet", "--short", "HEAD"): completed(
            ["symbolic-ref", "--quiet", "--short", "HEAD"], returncode=1
        ),
        ("config", "--get", "remote.one.atlassian-resolved"): completed(
            ["config", "--get", "remote.one.atlassian-resolved"], stdout="base\n"
        ),
        ("config", "--get", "remote.two.atlassian-resolved"): completed(
            ["config", "--get", "remote.two.atlassian-resolved"], stdout="base\n"
        ),
    }
    run_git, _ = fake_git(responses)

    result = GitRepositoryContext(tmp_path, run_git=run_git).read()

    assert result.current_branch is None
    assert result.upstream_remote is None
    assert result.default_remote is None


def test_detached_head_has_no_current_branch_or_upstream(tmp_path: Path) -> None:
    responses = {
        ("remote",): completed(["remote"]),
        ("symbolic-ref", "--quiet", "--short", "HEAD"): completed(
            ["symbolic-ref", "--quiet", "--short", "HEAD"], returncode=1
        ),
    }
    run_git, calls = fake_git(responses)

    result = GitRepositoryContext(tmp_path, run_git=run_git).read()

    assert result.current_branch is None
    assert result.upstream_remote is None
    assert not any(args[0] == "for-each-ref" for args, _ in calls)
