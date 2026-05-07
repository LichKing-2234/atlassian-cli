from typer.main import get_command

from atlassian_cli.cli import app
from tests.e2e.coverage_manifest import COVERAGE_MANIFEST


def discover_leaf_commands() -> set[str]:
    root = get_command(app)

    def walk(command, parts: tuple[str, ...]) -> set[str]:
        child_commands = getattr(command, "commands", {})
        if not child_commands:
            return {" ".join(parts)} if parts else set()

        commands: set[str] = set()
        for name, child in child_commands.items():
            commands.update(walk(child, (*parts, name)))
        return commands

    return walk(root, ())


def test_coverage_manifest_matches_cli_surface() -> None:
    assert set(COVERAGE_MANIFEST) == discover_leaf_commands()


def test_coverage_manifest_declares_owners_for_every_command() -> None:
    assert all(owner for owner in COVERAGE_MANIFEST.values())
