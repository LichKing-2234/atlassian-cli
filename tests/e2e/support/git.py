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

    def configure_identity(self) -> None:
        self.run("config", "user.name", "atlassian-cli-e2e")
        self.run("config", "user.email", "atlassian-cli-e2e@example.com")

    def create_commit(self, branch: str, file_name: str, content: str, message: str) -> None:
        self.run("checkout", "-b", branch)
        (self.root / file_name).write_text(content)
        self.run("add", file_name)
        self.run("commit", "-m", message)

    def push(self, branch: str) -> None:
        self.run("push", "-u", "origin", branch)

    def delete_remote_branch(self, branch: str) -> None:
        self.run("push", "origin", "--delete", branch)
