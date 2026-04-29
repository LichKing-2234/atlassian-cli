from typer.main import get_command

from atlassian_cli.cli import app
from tests.e2e.coverage_manifest import COVERAGE_MANIFEST


def discover_leaf_commands() -> set[str]:
    root = get_command(app)
    commands: set[str] = set()
    for product_name, product_cmd in root.commands.items():
        for group_name, group_cmd in product_cmd.commands.items():
            for leaf_name in getattr(group_cmd, "commands", {}):
                commands.add(f"{product_name} {group_name} {leaf_name}")
    return commands


def test_coverage_manifest_matches_cli_surface() -> None:
    assert set(COVERAGE_MANIFEST) == discover_leaf_commands()


def test_coverage_manifest_declares_owners_for_every_command() -> None:
    assert all(owner for owner in COVERAGE_MANIFEST.values())
