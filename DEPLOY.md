# WordPop / VideoEnglish deploy notes for Render

## Recommended: Render

1. Push this repo to GitHub.
2. In Render: **New > Blueprint** and select `render.yaml`, or create a Web Service manually:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Env vars (Blueprint 已写好)：
   - `APP_MODE=web`
   - `LOCAL_AUTO_USER=0`
   - `SECRET_KEY=<random>`
   - `INLINE_WORKER=1`
   - `DATABASE_URL=sqlite:///./db.sqlite3`
4. 配置 Neon 数据库（必做）：
   - Neon 复制连接串（Connection pooling 可开）
   - Render Dashboard → 你的 Web 服务（一般叫 `wordpop`）
   - 左侧 **Environment**
   - **Add Environment Variable**
   - Key: `DATABASE_URL`
   - Value: 粘贴 Neon 连接串（建议只保留 `?sslmode=require`）
   - Save → **Manual Deploy** → Deploy latest commit
5. Open `https://<service>.onrender.com/` → mobile app (`/app`).
6. 用户名密码注册/登录 → 词书刷词 / 阅读 / 生词练习 / PK。

若 Blueprint 创建时弹出 “Environment Variables” / “sync: false”，那里填 `DATABASE_URL` 即可。


## Dictionary + wordbooks (disk, not Neon)

- **ECDICT**: ship `app/assets/dictionaries/dictionary.db` (preferred) or `ecdict.csv` at repo root;
  build runs `python scripts/ensure_dictionary_db.py` to convert CSV → SQLite on the Render disk.
- **Wordbooks**: curated JSON under `app/assets/curated/wordbooks/*.json`. Study feed reads JSON;
  Neon/Postgres only stores catalog shells + user progress/stars (sparse rows when starring).
- **Neon `DATABASE_URL`**: accounts, reading progress, PK, vocab cards, wordbook memory — not full ECDICT/word lists.

## Neon DATABASE_URL

1. Neon → copy connection string (`?sslmode=require`)
2. Render → Web service `wordpop` → Environment → `DATABASE_URL`
3. Manual Deploy

## Why not Vercel alone

FastAPI + WebSocket PK + file uploads + background translation need a long-running server.
Use Render (or Railway/Fly) for the API. Vercel can host a static frontend later if you split the SPA.

## Local web mode

```bash
set APP_MODE=web
set LOCAL_AUTO_USER=0
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/app
