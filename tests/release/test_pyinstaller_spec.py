from pathlib import Path


def test_pyinstaller_spec_includes_prompt_toolkit_hiddenimports() -> None:
    spec = Path("atlassian.spec").read_text()

    assert 'hiddenimports=[' in spec
    assert '"prompt_toolkit"' in spec
    assert '"prompt_toolkit.key_binding"' in spec
    assert '"prompt_toolkit.keys"' in spec
    assert '"prompt_toolkit.layout"' in spec
    assert '"prompt_toolkit.layout.controls"' in spec
