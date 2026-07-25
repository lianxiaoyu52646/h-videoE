# WordPop / VideoEnglish deploy notes for Render

## Recommended: Render

1. Push this repo to GitHub.
2. In Render: **New > Blueprint** and select `render.yaml`, or create a Web Service manually:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Attach a Postgres database and set `DATABASE_URL` (Render injects it automatically with Blueprint).
4. Env vars:
   - `APP_MODE=web`
   - `LOCAL_AUTO_USER=0`
   - `SECRET_KEY=<random>`
   - `INLINE_WORKER=1`
5. Open `https://<service>.onrender.com/` → mobile app (`/app`).
6. 用户名密码注册/登录 → 词书刷词 / 阅读 / 生词练习 / PK。

## Dictionary asset

Keep `app/assets/dictionaries/dictionary.db` in the deploy image (already under `app/assets`).
If the DB is too large for git, upload it in the build step or mount from object storage and set the path accordingly.

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
