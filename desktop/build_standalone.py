"""Build a single-file VideoEnglish executable that can be shared and run by double-clicking."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist" / "VideoEnglish"
OUTPUT_EXE = ROOT / "dist" / "VideoEnglish.exe"
WORK_DIR = ROOT / "desktop" / "dist" / "pyinstaller-work-standalone"
SPEC_DIR = ROOT / "desktop" / "dist" / "pyinstaller-spec-standalone"
ADD_DATA_SEP = ";" if os.name == "nt" else ":"


def main() -> None:
    DIST_DIR.parent.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if OUTPUT_EXE.exists():
        OUTPUT_EXE.unlink()
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    if SPEC_DIR.exists():
        shutil.rmtree(SPEC_DIR)

    PyInstaller.__main__.run(
        [
            str(ROOT / "app" / "standalone_launcher.py"),
            "--name",
            "VideoEnglish",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--console",
            "--distpath",
            str(DIST_DIR.parent),
            "--workpath",
            str(WORK_DIR),
            "--specpath",
            str(SPEC_DIR),
            "--add-data",
            f"{ROOT / 'app' / 'static'}{ADD_DATA_SEP}app/static",
            "--add-data",
            f"{ROOT / 'app' / 'assets'}{ADD_DATA_SEP}app/assets",
            "--collect-submodules",
            "uvicorn",
            "--collect-submodules",
            "sqlalchemy",
            "--collect-submodules",
            "pydantic",
            "--hidden-import",
            "app.main",
            "--hidden-import",
            "app.worker",
            "--hidden-import",
            "app.desktop_runtime",
            "--runtime-hook",
            str(ROOT / "desktop" / "runtime_hook.py"),
        ]
    )
    print(f"\nStandalone build ready: {OUTPUT_EXE}")
    print("Share the single-file EXE. Recipients double-click VideoEnglish.exe.")


if __name__ == "__main__":
    main()
