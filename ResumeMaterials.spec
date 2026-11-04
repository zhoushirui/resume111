from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "web"), "web")],
    hiddenimports=["uvicorn.logging", "uvicorn.loops.asyncio",
                   "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name="ResumeMaterials", debug=False, strip=False, upx=False, console=True)
