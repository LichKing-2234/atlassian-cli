import tomllib
from pathlib import Path


def test_direct_runtime_imports_are_declared_dependencies() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies = {
        dependency.split(">", 1)[0].split("=", 1)[0].split("<", 1)[0].strip().lower()
        for dependency in pyproject["project"]["dependencies"]
    }

    assert "click" in dependencies
