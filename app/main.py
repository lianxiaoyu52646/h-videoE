from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import database, schemas, security
from app.config import settings
from app.routers import app_data, bilibili_auth, jobs, practice, pk, readings, review, videos, vocabulary, wordbooks
from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_runtime_dirs()
    database.init_db()
    if settings.local_auto_user:
        security.ensure_default_user_exists()
    # Preload all bundled KyleBing wordbooks into SQLite for every user.
    if settings.auto_install_wordbooks:
        try:
            from sqlmodel import Session
            from app.services import wordbook_catalog

            with Session(database.engine) as session:
                wordbook_catalog.ensure_bundled_wordbooks_for_all_users(session)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("bundled wordbook preinstall failed")
    from app.services import reading_processor
    import asyncio

    reading_processor.set_event_loop(asyncio.get_running_loop())
    reading_processor.resume_pending_translations()
    try:
        from app.services import book_translate_jobs

        book_translate_jobs.pause_stale_checkpoint()
    except Exception:
        import logging

        logging.getLogger(__name__).exception("book translate checkpoint resume mark failed")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_alias_and_auth(request: Request, call_next):
    path = request.scope["path"]
    if path == "/api/v1" or path.startswith("/api/v1/"):
        suffix = path[len("/api/v1") :]
        request.scope["path"] = f"/api{suffix}" if suffix else "/api"
        request.scope["raw_path"] = request.scope["path"].encode("utf-8")
        path = request.scope["path"]

    if security.is_api_request_path(path) and not security.is_public_api_path(path):
        user = security.resolve_request_user(request)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        request.state.user = user
        token = security.set_current_user(user.id)
        try:
            return await call_next(request)
        finally:
            security.reset_current_user(token)
    response = await call_next(request)
    if settings.desktop_hot_reload and path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
app.mount("/mobile", StaticFiles(directory=str(settings.project_dir / "mobile" / "www")), name="mobile")


def _static_page(name: str) -> FileResponse:
    return FileResponse(settings.static_dir / name)


def _mobile_app() -> FileResponse:
    resp = FileResponse(settings.static_dir / "m" / "index.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.get("/")
def home():
    # Web / cloud product lands on mobile-first shell; desktop keeps classic home.
    if settings.desktop_mode:
        return _static_page("index.html")
    return _mobile_app()


@app.get("/app")
def mobile_app_page():
    return _mobile_app()


@app.get("/learn")
def learn_page():
    if not settings.desktop_mode:
        return RedirectResponse("/app", status_code=307)
    return _static_page("learn.html")


@app.get("/vocab")
def vocab_page():
    if not settings.desktop_mode:
        return RedirectResponse("/app", status_code=307)
    return _static_page("vocab.html")


@app.get("/practice")
def practice_page():
    return RedirectResponse("/vocab" if settings.desktop_mode else "/app", status_code=307)


@app.get("/read")
def read_page():
    return FileResponse(settings.static_dir / "read.html")


@app.get("/reader")
def reader_page():
    return FileResponse(settings.static_dir / "reader.html")


@app.get("/wordbooks")
def wordbooks_page():
    if not settings.desktop_mode:
        return RedirectResponse("/app", status_code=307)
    return FileResponse(settings.static_dir / "wordbooks.html")


@app.get("/wordbook")
def wordbook_detail_page():
    if not settings.desktop_mode:
        return RedirectResponse("/app", status_code=307)
    return FileResponse(settings.static_dir / "wordbook.html")


@app.get("/login")
def login_page():
    if settings.desktop_mode:
        return RedirectResponse("/", status_code=307)
    return FileResponse(settings.static_dir / "login.html")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/app-shell", response_model=schemas.AppShellRead)
def app_shell():
    return schemas.AppShellRead(
        app_name=settings.app_name,
        app_mode=settings.app_mode,
        desktop_mode=settings.desktop_mode,
        supports_login=settings.show_auth_ui,
        supports_extension=settings.show_extension_ui,
        profile_name=settings.desktop_profile_name,
        desktop_base_url=settings.desktop_base_url,
        mobile_home=not settings.desktop_mode,
        features=["reading", "wordbooks", "vocab", "pk"],
    )


def _load_app_version() -> schemas.AppVersionRead:
    """Prefer static/m/app-version.json; env vars override APK URL / force flag."""
    import json
    import os

    data = {
        "web_content_version": "0",
        "android_version_code": 1,
        "android_version_name": "1.0.0",
        "android_apk_url": "",
        "notes": "",
        "force_apk": False,
    }
    path = settings.static_dir / "m" / "app-version.json"
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update({k: raw[k] for k in data if k in raw})
        except Exception:
            pass
    env_url = (os.getenv("ANDROID_APK_URL") or "").strip()
    if env_url:
        data["android_apk_url"] = env_url
    env_web = (os.getenv("WEB_CONTENT_VERSION") or "").strip()
    if env_web:
        data["web_content_version"] = env_web
    if (os.getenv("ANDROID_FORCE_UPDATE") or "").strip().lower() in {"1", "true", "yes"}:
        data["force_apk"] = True
    return schemas.AppVersionRead(**data)


@app.get("/api/app-version", response_model=schemas.AppVersionRead)
def app_version():
    return _load_app_version()


@app.get("/api/tts")
def proxy_english_tts(q: str = ""):
    """Same-origin English TTS audio for WebView (avoids blocked third-party hosts)."""
    import urllib.parse
    import urllib.request

    from fastapi.responses import Response

    word = (q or "").strip()
    if not word or len(word) > 80:
        return JSONResponse({"detail": "invalid word"}, status_code=400)
    # Prefer Youdao (CN-friendly); fallback Google translate TTS.
    candidates = [
        "https://dict.youdao.com/dictvoice?type=2&audio=" + urllib.parse.quote(word),
        "https://dict.youdao.com/dictvoice?type=1&audio=" + urllib.parse.quote(word),
        "https://translate.googleapis.com/translate_tts?ie=UTF-8&client=tw-ob&tl=en&q="
        + urllib.parse.quote(word),
    ]
    last_err = "tts unavailable"
    for url in candidates:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 WordPopTTS/1.0",
                    "Accept": "*/*",
                    "Referer": "https://dict.youdao.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type") or "audio/mpeg"
            if not data or len(data) < 64:
                continue
            return Response(
                content=data,
                media_type=ctype.split(";")[0].strip() or "audio/mpeg",
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except Exception as e:
            last_err = str(e)
            continue
    return JSONResponse({"detail": last_err}, status_code=502)


app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(readings.router)
app.include_router(vocabulary.router)
app.include_router(review.router)
app.include_router(practice.router)
app.include_router(bilibili_auth.router)
app.include_router(wordbooks.router)
app.include_router(jobs.router)
app.include_router(app_data.router)
app.include_router(pk.router)
