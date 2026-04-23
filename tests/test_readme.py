from pathlib import Path


def test_readme_mentions_model_first_normalized_output() -> None:
    readme = Path("README.md").read_text()

    assert "resource-shaped payloads" in readme
    assert "raw-json" in readme
    assert "raw-yaml" in readme
    assert "Single-resource commands return a resource object." in readme
    assert "Collection commands return explicit envelopes" in readme
