from pathlib import Path

def dump_around(path, needles, radius=40):
    text = Path(path).read_text(encoding='utf-8')
    lines = text.splitlines()
    print(f'\n========== {path} ==========')
    seen = set()
    for n in needles:
        for i, line in enumerate(lines):
            if n in line:
                start = max(0, i-2)
                end = min(len(lines), i+radius)
                key = (start, end, n)
                if key in seen:
                    continue
                seen.add(key)
                print(f'\n----- {n} @ line {i+1} -----')
                for j in range(start, end):
                    print(f'{j+1:5}|{lines[j]}')

dump_around(r'D:\lian\praPro\h-videoE\app\static\m\app.js', [
    'reviewDueCard','paintDueCardFast','/api/review','openVocabBook','请求失败','function api(',
    'renderStudy','skeleton','is-away','study-top','pageSize','dueCard','会','不会','paintDue'
])
