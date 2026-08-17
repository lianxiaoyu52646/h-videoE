import sys
from pathlib import Path
root = Path(r"D:\lian\praPro\h-videoE")
sys.path.insert(0, str(root))
# use venv if present
venv = root / ".venv" / "Scripts" / "python.exe"
print("venv", venv.exists())
