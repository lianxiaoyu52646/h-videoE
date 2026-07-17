from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import database, schemas, security
from app.config import settings
from app.routers import app_data, bilibili_auth, jobs, practice, readings, review, videos, vocabulary, wordbooks
from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_runtime_dirs()
    database.init_db()
    if settings.local_auto_user:
        security.ensure_default_user_exists()
    from app.services import reading_processor
    import asyncio

    reading_processor.set_event_loop(asyncio.get_running_loop())
    reading_processor.resume_pending_translations()
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


def _static_page(name: str) -> FileResponse:
    return FileResponse(settings.static_dir / name)


@app.get("/")
def home():
    return _static_page("index.html")


@app.get("/learn")
def learn_page():
    return _static_page("learn.html")


@app.get("/vocab")
def vocab_page():
    return _static_page("vocab.html")


@app.get("/practice")
def practice_page():
    return RedirectResponse("/vocab", status_code=307)


@app.get("/read")
def read_page():
    return FileResponse(settings.static_dir / "read.html")


@app.get("/reader")
def reader_page():
    return FileResponse(settings.static_dir / "reader.html")


@app.get("/wordbooks")
def wordbooks_page():
    return FileResponse(settings.static_dir / "wordbooks.html")


@app.get("/wordbook")
def wordbook_detail_page():
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
    )


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
