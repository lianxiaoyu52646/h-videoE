from __future__ import annotations

import os
from pathlib import Path

import PyInstaller.__main__


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "desktop" / "sidecar"
WORK_DIR = ROOT / "desktop" / "dist" / "pyinstaller-work"
SPEC_DIR = ROOT / "desktop" / "dist" / "pyinstaller-spec"
ADD_DATA_SEP = ";" if os.name == "nt" else ":"


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    PyInstaller.__main__.run(
        [
            str(ROOT / "app" / "desktop_runtime.py"),
            "--name",
            "videoenglish-backend",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--distpath",
            str(DIST_DIR),
            "--workpath",
            str(WORK_DIR),
            "--specpath",
            str(SPEC_DIR),
            "--add-data",
            f"{ROOT / 'app' / 'static'}{ADD_DATA_SEP}app/static",
            "--add-data",
            f"{ROOT / 'app' / 'assets'}{ADD_DATA_SEP}app/assets",
        ]
    )


if __name__ == "__main__":
    main()
