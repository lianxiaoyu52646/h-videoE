import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    root = Path(sys.executable).resolve().parent
    if (root / "app").exists():
        sys.path.insert(0, str(root))
    meipass = Path(getattr(sys, "_MEIPASS", root))
    if (meipass / "app").exists():
        sys.path.insert(0, str(meipass))
