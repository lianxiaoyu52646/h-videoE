from pathlib import Path

def dump_around(path, needles, radius=50):
    text = Path(path).read_text(encoding='utf-8')
    lines = text.splitlines()
    print(f'\n========== {path} ==========')
    printed = set()
    for n in needles:
        found = False
        for i, line in enumerate(lines):
            if n in line:
                found = True
                start = max(0, i-3)
                end = min(len(lines), i+radius)
                key = (start, end)
                if key in printed:
                    continue
                printed.add(key)
                print(f'\n----- {n} @ line {i+1} -----')
                for j in range(start, end):
                    print(f'{j+1:5}|{lines[j]}')
        if not found:
            print(f'\n----- {n} NOT FOUND -----')

dump_around(r'D:\lian\praPro\h-videoE\app\static\m\app.js', [
    'async function api',
    'function api(',
    'function openVocabBook',
    'function renderStudy',
    'function showStudySkeleton',
    'STUDY',
    'is-away',
    'heroIn',
    'pageSize',
])
