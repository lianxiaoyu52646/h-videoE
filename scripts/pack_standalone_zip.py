import zipfile
from pathlib import Path

root = Path('dist/VideoEnglish')
out = Path('dist/VideoEnglish.zip')
if out.exists():
    out.unlink()

with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(root.rglob('*')):
        if path.is_file():
            rel = path.relative_to(root)
            z.write(path, arcname=f'VideoEnglish/{rel.as_posix()}')

print(out.exists(), out.stat().st_size)
