from pathlib import Path
t = Path(r"D:\lian\praPro\h-videoE\app\crud.py").read_text(encoding="utf-8")
i = t.find("def review_vocab")
print(t[i:i+1200])
print("---- vocab_to_read ----")
j = t.find("def vocab_to_read")
print(t[j:j+700])
