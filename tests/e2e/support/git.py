import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitSandbox:
    root: Path

    @classmethod
    def clone(cls, clone_url: str, destination: Path) -> "GitSandbox":
        subprocess.run(
            ["git", "clone", clone_url, str(destination)],
            check=True,
            capture_output=True,
            text=True,
        )
        return cls(root=destination)

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def has_head(self) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def configure_identity(self) -> None:
        self.run("config", "user.name", "atlassian-cli-e2e")
        self.run("config", "user.email", "atlassian-cli-e2e@example.com")

    def create_initial_commit(self, branch: str, file_name: str, content: str, message: str) -> None:
        self.run("checkout", "--orphan", branch)
        (self.root / file_name).write_text(content)
        self.run("add", file_name)
        self.run("commit", "-m", message)

    def create_commit(self, branch: str, file_name: str, content: str, message: str) -> None:
        self.run("checkout", "-b", branch)
        (self.root / file_name).write_text(content)
        self.run("add", file_name)
        self.run("commit", "-m", message)

    def push(self, branch: str) -> None:
        self.run("push", "-u", "origin", branch)

    def push_head_to_branch(self, branch: str) -> None:
        self.run("push", "origin", f"HEAD:refs/heads/{branch}")

    def delete_remote_branch(self, branch: str) -> None:
        result = subprocess.run(
            ["git", "push", "origin", "--delete", branch],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        stderr = (result.stderr or "").lower()
        if result.returncode != 0 and "remote ref does not exist" not in stderr:
            raise AssertionError(result.stderr.strip() or result.stdout.strip())
