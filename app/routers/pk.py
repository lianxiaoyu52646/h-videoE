"""PK battle REST + WebSocket endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import database, models, security
from app.config import settings
from app.services import pk_rooms

router = APIRouter(tags=["pk"])


class CreateRoomRequest(BaseModel):
    mode: str = Field(default="bot", pattern="^(bot|pvp)$")
    wordbook_id: int | None = None


class JoinRoomRequest(BaseModel):
    code: str


def _user_label(user: models.User) -> str:
    return user.username or user.display_name or f"玩家{user.id}"


@router.post("/api/pk/rooms")
async def create_pk_room(
    body: CreateRoomRequest,
    user: models.User = Depends(security.get_current_user),
):
    room = await pk_rooms.create_room(
        user_id=user.id,
        display_name=_user_label(user),
        mode=body.mode,
        wordbook_id=body.wordbook_id,
    )
    return pk_rooms.public_state(room, for_user=user.id)


@router.post("/api/pk/rooms/join")
async def join_pk_room(
    body: JoinRoomRequest,
    user: models.User = Depends(security.get_current_user),
):
    try:
        room = await pk_rooms.join_room(
            code=pk_rooms.normalize_code(body.code),
            user_id=user.id,
            display_name=_user_label(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return pk_rooms.public_state(room, for_user=user.id)


@router.get("/api/pk/rooms/{code}")
def get_pk_room(
    code: str,
    user: models.User = Depends(security.get_current_user),
):
    room = pk_rooms.get_room(code)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在或已过期")
    return pk_rooms.public_state(room, for_user=user.id)


@router.websocket("/api/pk/ws/{code}")
async def pk_websocket(websocket: WebSocket, code: str):
    await websocket.accept()
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.auth_cookie_name)
    user = None
    with Session(database.engine) as session:
        if token:
            user = security.authenticate_token(session, token)
        if user is None and settings.local_auto_user:
            user = security.ensure_default_user(session)

    if user is None:
        await websocket.send_json({"event": "error", "data": {"detail": "未登录"}})
        await websocket.close(code=4401)
        return

    norm = pk_rooms.normalize_code(code)
    room = pk_rooms.get_room(norm)
    if not room:
        await websocket.send_json({"event": "error", "data": {"detail": "房间不存在或已过期"}})
        await websocket.close(code=4404)
        return

    try:
        if user.id not in room.players:
            await pk_rooms.join_room(code=norm, user_id=user.id, display_name=_user_label(user))
            room = pk_rooms.get_room(norm)
        await pk_rooms.attach_ws(room, user.id, websocket)
    except ValueError as exc:
        await websocket.send_json({"event": "error", "data": {"detail": str(exc)}})
        await websocket.close()
        return

    try:
        while True:
            msg = await websocket.receive_json()
            action = (msg.get("action") or "").strip()
            room = pk_rooms.get_room(norm) or room
            try:
                if action == "ready":
                    await pk_rooms.set_ready(room, user.id, True)
                elif action == "unready":
                    await pk_rooms.set_ready(room, user.id, False)
                elif action == "answer":
                    await pk_rooms.submit_answer(room, user.id, int(msg.get("choice", -1)))
                elif action == "ping":
                    await websocket.send_json({"event": "pong", "data": {}})
                else:
                    await websocket.send_json({"event": "error", "data": {"detail": "未知操作"}})
            except ValueError as exc:
                await websocket.send_json({"event": "error", "data": {"detail": str(exc)}})
    except WebSocketDisconnect:
        player = room.players.get(user.id)
        if player:
            pk_rooms.mark_offline(room, user.id)
