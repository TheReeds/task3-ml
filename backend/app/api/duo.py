"""Módulo Dúo: salas por código (REST) y partida en tiempo real (WebSocket).

Protocolo WebSocket `/duo/ws/{code}?token=<token anónimo>[&device_id=<X-Device-Id>]`:
  cliente → servidor  {"action": "start_round"}
                      {"action": "describe", "text": "..."}
                      {"action": "guess", "image_id": 12}
                      {"action": "consent", "value": true|false}
                      {"action": "skip"}            el descriptor pasa la imagen
                      {"action": "leave"}           cierra la sala para ambos
  servidor → cliente  {"type": "state", ...}   vista personalizada tras cada cambio
                      {"type": "error", "status": 409, "detail": "..."}

El registro de conexiones vive en memoria del proceso: en producción con varios workers
habría que sustituirlo por un canal compartido (p. ej. Redis pub/sub).
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.api.deps import DB, CurrentContributor
from app.config import get_settings
from app.db import SessionLocal
from app.models import Contributor
from app.services import duo, metrics
from app.services.auth import contributor_by_token

router = APIRouter(prefix="/duo", tags=["duo"])


class Hub:
    """Conexiones activas por sala y asiento."""

    def __init__(self) -> None:
        self.rooms: dict[str, dict[int, WebSocket]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def lock(self, code: str) -> asyncio.Lock:
        return self.locks.setdefault(code, asyncio.Lock())

    def connected(self, code: str) -> set[int]:
        return set(self.rooms.get(code, {}))

    async def broadcast(self, code: str) -> None:
        for seat, ws in list(self.rooms.get(code, {}).items()):
            state = await run_in_threadpool(_state, code, seat, self.connected(code))
            try:
                await ws.send_json(state)
            except RuntimeError:
                self.rooms.get(code, {}).pop(seat, None)


hub = Hub()


def _state(code: str, seat: int, connected: set[int]) -> dict:
    with SessionLocal() as db:
        return duo.state_for(db, duo.get_room(db, code), seat, connected)


def _raise(e: duo.DuoError):
    raise HTTPException(e.status, e.detail) from e


# --- REST ------------------------------------------------------------------------


@router.post("/rooms", status_code=201)
def create_room(db: DB, contributor: CurrentContributor, lang: str | None = None):
    """Crea una sala y devuelve su código para compartir con la otra persona."""
    room = duo.create_room(db, contributor, lang or get_settings().default_lang)
    return {"code": room.code, "seat": 0}


@router.post("/rooms/{code}/join")
async def join_room(code: str, db: DB, contributor: CurrentContributor):
    try:
        room = duo.join_room(db, code, contributor)
        seat = duo.player_of(db, room, contributor).seat
    except duo.DuoError as e:
        _raise(e)
    await hub.broadcast(room.code)
    return {"code": room.code, "seat": seat}


@router.get("/rooms/{code}")
def room_state(code: str, db: DB, contributor: CurrentContributor):
    try:
        room = duo.get_room(db, code)
        seat = duo.player_of(db, room, contributor).seat
    except duo.DuoError as e:
        _raise(e)
    return duo.state_for(db, room, seat, hub.connected(room.code))


@router.put("/rooms/{code}/consent")
async def set_consent(code: str, db: DB, contributor: CurrentContributor,
                      consent: Annotated[bool, Body(embed=True)]):
    """Consentimiento para capturar mis descripciones. Revocarlo retira lo ya capturado."""
    try:
        room = duo.get_room(db, code)
        duo.set_consent(db, room, contributor, consent)
    except duo.DuoError as e:
        _raise(e)
    await hub.broadcast(room.code)
    return {"consent": consent}


@router.post("/rooms/{code}/leave")
async def leave_room(code: str, db: DB, contributor: CurrentContributor):
    """Salir de la sala la cierra para ambos participantes."""
    try:
        room = duo.get_room(db, code)
        duo.leave_room(db, room, contributor)
    except duo.DuoError as e:
        _raise(e)
    await hub.broadcast(room.code)
    return {"code": room.code, "status": "closed"}


# --- WebSocket --------------------------------------------------------------------


def _authenticate(code: str, token: str | None) -> tuple[str, int, object]:
    with SessionLocal() as db:
        contributor = contributor_by_token(db, token)
        if contributor is None:
            raise duo.DuoError(401, "Token no reconocido")
        room = duo.get_room(db, code)
        return room.code, duo.player_of(db, room, contributor).seat, contributor.id


def _act(code: str, contributor_id, msg: dict, device_id: str | None = None) -> None:
    with SessionLocal() as db:
        room = duo.get_room(db, code)
        contributor = db.get(Contributor, contributor_id)
        match msg.get("action"):
            case "start_round":
                duo.player_of(db, room, contributor)
                duo.start_round(db, room)
            case "describe":
                duo.describe(db, room, contributor, str(msg.get("text", "")))
            case "guess":
                rnd = duo.guess(db, room, contributor, int(msg.get("image_id", -1)))
                metrics.record(db, "duo.round_done", "duo", device_id=device_id,
                               contributor_id=contributor.id,
                               props={"success": rnd.success, "difficulty": rnd.difficulty})
                db.commit()
            case "consent":
                duo.set_consent(db, room, contributor, bool(msg.get("value")))
            case "skip":
                duo.skip(db, room, contributor)
            case "leave":
                duo.leave_room(db, room, contributor)
            case other:
                raise duo.DuoError(422, f"Acción desconocida: {other!r}")


@router.websocket("/ws/{code}")
async def play(websocket: WebSocket, code: str, token: str | None = None,
               device_id: str | None = None):
    try:
        code, seat, contributor_id = await run_in_threadpool(_authenticate, code, token)
    except duo.DuoError as e:
        await websocket.close(code=4000 + e.status, reason=e.detail)
        return
    await websocket.accept()
    hub.rooms.setdefault(code, {})[seat] = websocket
    await hub.broadcast(code)
    try:
        while True:
            msg = await websocket.receive_json()
            try:
                async with hub.lock(code):  # las acciones de una sala se serializan
                    await run_in_threadpool(_act, code, contributor_id, msg, device_id)
            except (duo.DuoError, ValueError, TypeError) as e:
                status, detail = (e.status, e.detail) if isinstance(e, duo.DuoError) else (422, str(e))
                await websocket.send_json({"type": "error", "status": status, "detail": detail})
                continue
            await hub.broadcast(code)
    except WebSocketDisconnect:
        pass
    finally:
        if hub.rooms.get(code, {}).get(seat) is websocket:
            hub.rooms[code].pop(seat)
        await hub.broadcast(code)
