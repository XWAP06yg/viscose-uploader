# -*- mode: python ; coding: utf-8 -*-
import inspect
from pathlib import Path

block_cipher = None

spec_dir = Path(inspect.getfile(inspect.currentframe())).resolve().parent
project_root = spec_dir.parent

a = Analysis(
    [str(project_root / "viscose" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "viscose.auth",
        "viscose.cli",
        "viscose.commands",
        "viscose.update",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)  # type: ignore[name-defined]
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # type: ignore[name-defined]
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="viscose",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)  # type: ignore[name-defined]
