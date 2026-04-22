from pathlib import Path


PROJECT_ROOT = Path.cwd().resolve()
SRC_ROOT = PROJECT_ROOT / "src"


a = Analysis(
    [str(SRC_ROOT / "atlassian_cli" / "main.py")],
    pathex=[str(SRC_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name="atlassian",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
