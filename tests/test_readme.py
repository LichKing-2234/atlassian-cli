from pathlib import Path


def test_readme_mentions_markdown_default_and_interactive_lists() -> None:
    readme = Path("README.md").read_text()

    assert "markdown" in readme
    assert "interactive" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme
    assert "table" not in readme


def test_readme_mentions_interactive_preview_browser() -> None:
    readme = Path("README.md").read_text()

    assert "live preview" in readme.lower()
    assert "j/k move  n/p page  / filter  r refresh  enter detail  b/esc back  q quit" in readme
    assert "bottom preview" in readme.lower()
