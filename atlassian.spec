from pathlib import Path


PROJECT_ROOT = Path.cwd().resolve()
SRC_ROOT = PROJECT_ROOT / "src"


a = Analysis(
    [str(SRC_ROOT / "atlassian_cli" / "main.py")],
    pathex=[str(SRC_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "prompt_toolkit",
        "prompt_toolkit.key_binding",
        "prompt_toolkit.keys",
        "prompt_toolkit.layout",
        "prompt_toolkit.layout.controls",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="atlassian",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="atlassian",
)
