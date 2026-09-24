"""Módulo Dúo (§6.6): juego colaborativo de descripción e identificación de imágenes.

Flujo de una ronda: el descriptor recibe una imagen y la describe en la lengua objetivo; el
adivinador ve cuatro imágenes y elige una. Ambos aciertan o ambos fallan. Los roles se alternan.

Distractores: tres imágenes de otros conceptos con similitud CLIP intermedia respecto del
objetivo. La dificultad (qué tan parecidos son) se ajusta por sala con una escalera ponderada
que converge a un acierto de ~65 %, dentro del rango objetivo 55–75 %.

La descripción se guarda como contribución `new_sentence` solo si el descriptor dio su
consentimiento; revocarlo retira sus textos de la revisión y de la exportación.
"""

import random
import secrets
import unicodedata
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.models import (
    Contribution,
    Contributor,
    DuoImage,
    DuoPlayer,
    DuoRoom,
    DuoRound,
    Embedding,
    Lexeme,
)
from app.services.corpus import is_current, media_url

CLIP_ID = "clip-vit-b32"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I
TARGET_SUCCESS = 0.65
STEP_UP = 0.07  # tras un acierto: distractores más parecidos
STEP_DOWN = STEP_UP * TARGET_SUCCESS / (1 - TARGET_SUCCESS)  # tras un fallo (≈0.13)
INITIAL_DIFFICULTY = 0.4
MAX_DESCRIPTION = 280


class DuoError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status, self.detail = status, detail


# --- salas -----------------------------------------------------------------------


def create_room(db: Session, contributor: Contributor, lang: str) -> DuoRoom:
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not db.scalar(select(func.count()).where(DuoRoom.code == code)):
            break
    room = DuoRoom(code=code, lang=lang, status="waiting")
    db.add(room)
    db.flush()
    db.add(DuoPlayer(room_id=room.id, contributor_id=contributor.id, seat=0))
    db.commit()
    return room


def get_room(db: Session, code: str) -> DuoRoom:
    room = db.scalars(select(DuoRoom).where(DuoRoom.code == code.upper())).first()
    if room is None:
        raise DuoError(404, "Sala no encontrada")
    return room


def player_of(db: Session, room: DuoRoom, contributor: Contributor) -> DuoPlayer:
    p = db.scalars(select(DuoPlayer).where(DuoPlayer.room_id == room.id,
                                           DuoPlayer.contributor_id == contributor.id)).first()
    if p is None:
        raise DuoError(403, "No participas en esta sala")
    return p


def join_room(db: Session, code: str, contributor: Contributor) -> DuoRoom:
    room = get_room(db, code)
    if room.status == "closed":
        raise DuoError(409, "La sala está cerrada")
    seats = {p.contributor_id: p.seat for p in room.players}
    if contributor.id in seats:
        return room  # reconexión
    if len(seats) >= 2:
        raise DuoError(409, "La sala ya tiene dos participantes")
    db.add(DuoPlayer(room_id=room.id, contributor_id=contributor.id, seat=1))
    room.status = "ready"
    db.commit()
    db.refresh(room)
    return room


def set_consent(db: Session, room: DuoRoom, contributor: Contributor, consent: bool) -> None:
    player = player_of(db, room, contributor)
    player.consent = consent
    if not consent:
        # Revocación: se retiran los textos ya capturados de este participante en la sala
        round_ids = select(DuoRound.contribution_id).where(
            DuoRound.room_id == room.id, DuoRound.describer_seat == player.seat,
            DuoRound.contribution_id.is_not(None))
        db.execute(update(Contribution).where(
            Contribution.id.in_(round_ids), Contribution.status.in_(("pending", "accepted"))
        ).values(status="withdrawn", payload={"withdrawn": True}))
        # la ronda en curso conserva su texto para poder terminarse, pero ya no se capturará
        db.execute(update(DuoRound).where(
            DuoRound.room_id == room.id, DuoRound.describer_seat == player.seat, DuoRound.phase == "done"
        ).values(description=None))
    db.commit()


# --- rondas ----------------------------------------------------------------------


def current_round(db: Session, room: DuoRoom) -> DuoRound | None:
    return db.scalars(
        select(DuoRound).where(DuoRound.room_id == room.id).order_by(DuoRound.number.desc()).limit(1)
    ).first()


def next_difficulty(prev: DuoRound | None) -> float:
    if prev is None or prev.success is None:
        return prev.difficulty if prev else INITIAL_DIFFICULTY
    step = STEP_UP if prev.success else -STEP_DOWN
    return round(min(0.95, max(0.05, prev.difficulty + step)), 3)


def _image_vectors(db: Session, lang: str) -> tuple[list[DuoImage], np.ndarray]:
    rows = db.execute(
        select(DuoImage, Embedding.vector)
        .join(Embedding, (Embedding.owner_type == "image") & (Embedding.owner_id == DuoImage.id))
        .where(DuoImage.lang == lang, DuoImage.active, Embedding.model == CLIP_ID)
        .order_by(DuoImage.id)
    ).all()
    if len({r[0].concept_lemma for r in rows}) < 4:
        raise DuoError(503, "El catálogo de imágenes no tiene suficientes conceptos")
    return [r[0] for r in rows], np.stack([np.asarray(r[1], dtype=np.float32) for r in rows])


def choose_distractors(images: list[DuoImage], mat: np.ndarray, target_idx: int, difficulty: float,
                       rng: random.Random) -> list[DuoImage]:
    """Tres distractores de conceptos distintos entre sí y del objetivo.

    Se toma, por concepto, la imagen más parecida al objetivo; los conceptos se ordenan por esa
    similitud y se muestrea en una ventana centrada en el cuantil `difficulty` (0 = lo más
    distinto, 1 = lo más parecido), evitando tanto la trivialidad como la indistinguibilidad.
    """
    target = images[target_idx]
    sims = mat @ mat[target_idx]
    best: dict[str, int] = {}
    for i, img in enumerate(images):
        if img.concept_lemma == target.concept_lemma:
            continue
        if img.concept_lemma not in best or sims[i] > sims[best[img.concept_lemma]]:
            best[img.concept_lemma] = i
    ranked = sorted(best.values(), key=lambda i: sims[i])  # de menos a más parecido
    n = len(ranked)
    width = max(3, round(n * 0.3))
    center = round(difficulty * (n - 1))
    lo = min(max(0, center - width // 2), n - width)
    window = ranked[lo : lo + width]
    return [images[i] for i in rng.sample(window, 3)]


def start_round(db: Session, room: DuoRoom, rng: random.Random | None = None) -> DuoRound:
    rng = rng or random.Random()
    if room.status != "ready":
        raise DuoError(409, "Se necesitan dos participantes para jugar")
    prev = current_round(db, room)
    if prev is not None and prev.phase != "done":
        raise DuoError(409, "La ronda actual no ha terminado")
    images, mat = _image_vectors(db, room.lang)
    used = set(db.scalars(select(DuoRound.target_image_id).where(DuoRound.room_id == room.id)))
    fresh = [i for i, img in enumerate(images) if img.id not in used] or list(range(len(images)))
    target_idx = rng.choice(fresh)
    difficulty = next_difficulty(prev)
    options = [images[target_idx], *choose_distractors(images, mat, target_idx, difficulty, rng)]
    rng.shuffle(options)
    number = (prev.number + 1) if prev else 1
    rnd = DuoRound(room_id=room.id, number=number, describer_seat=(number - 1) % 2,
                   target_image_id=images[target_idx].id, option_ids=[o.id for o in options],
                   difficulty=difficulty, phase="describing")
    db.add(rnd)
    db.commit()
    return rnd


def _strip_accents(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def describe(db: Session, room: DuoRoom, contributor: Contributor, text: str) -> DuoRound:
    player = player_of(db, room, contributor)
    rnd = current_round(db, room)
    if rnd is None or rnd.phase != "describing":
        raise DuoError(409, "No hay una imagen esperando descripción")
    if player.seat != rnd.describer_seat:
        raise DuoError(403, "En esta ronda te toca adivinar")
    text = " ".join(text.split())
    if not 1 <= len(text) <= MAX_DESCRIPTION:
        raise DuoError(422, f"La descripción debe tener entre 1 y {MAX_DESCRIPTION} caracteres")
    target = db.get(DuoImage, rnd.target_image_id)
    if _strip_accents(target.concept_es) in _strip_accents(text).split():
        raise DuoError(422, "Describe la imagen en la lengua, sin nombrarla en español")
    rnd.description, rnd.phase = text, "guessing"
    db.commit()
    return rnd


def guess(db: Session, room: DuoRoom, contributor: Contributor, image_id: int) -> DuoRound:
    player = player_of(db, room, contributor)
    rnd = current_round(db, room)
    if rnd is None or rnd.phase != "guessing":
        raise DuoError(409, "No hay una descripción esperando respuesta")
    if player.seat == rnd.describer_seat:
        raise DuoError(403, "En esta ronda te toca describir")
    if image_id not in rnd.option_ids:
        raise DuoError(422, "La imagen no está entre las opciones")
    rnd.chosen_image_id, rnd.success = image_id, image_id == rnd.target_image_id
    rnd.phase, rnd.ended_at = "done", datetime.now(UTC)
    room.score += int(rnd.success)

    describer = next(p for p in room.players if p.seat == rnd.describer_seat)
    if describer.consent:
        target = db.get(DuoImage, rnd.target_image_id)
        c = Contribution(
            contributor_id=describer.contributor_id, lang=room.lang, type="new_sentence",
            target_type="duo_round", target_id=rnd.id, status="pending",
            payload={"proposed": rnd.description, "image_id": target.id,
                     "image_url": media_url(target.file_path), "concept_lemma": target.concept_lemma,
                     "concept_es": target.concept_es, "understood": rnd.success},
        )
        db.add(c)
        db.flush()
        rnd.contribution_id = c.id
    db.commit()
    return rnd


# --- vistas ----------------------------------------------------------------------


def hints(db: Session, lang: str, concept_lemma: str, k: int = 5) -> list[dict]:
    """Panel auxiliar del descriptor: el lema del concepto y lemas relacionados del corpus."""
    model = get_adapter().embedding_model(lang)
    rows = db.execute(
        select(Lexeme, Embedding.vector)
        .join(Embedding, (Embedding.owner_type == "lexeme") & (Embedding.owner_id == Lexeme.id))
        .where(Lexeme.lang == lang, is_current(Lexeme), Embedding.model == model,
               ~Lexeme.is_function_word, Lexeme.frequency >= 5)
    ).all()
    by_lemma = {r[0].lemma: (r[0], np.asarray(r[1], dtype=np.float32)) for r in rows}
    if concept_lemma not in by_lemma:
        return []
    target_lex, tv = by_lemma[concept_lemma]
    lemmas = [lm for lm in by_lemma if lm != concept_lemma]
    mat = np.stack([by_lemma[lm][1] for lm in lemmas])
    sims = mat @ tv / (np.linalg.norm(mat, axis=1) * np.linalg.norm(tv) + 1e-9)
    related = [by_lemma[lemmas[i]][0] for i in np.argsort(-sims)[:k]]
    return [{"lemma": lx.lemma, "gloss": lx.gloss} for lx in [target_lex, *related]]


def _image_out(img: DuoImage, reveal_concept: bool = False) -> dict:
    out = {"id": img.id, "url": media_url(img.file_path),
           "attribution": {"author": img.author, "license": img.license, "source": img.source_url}}
    if reveal_concept:
        out |= {"concept_lemma": img.concept_lemma, "concept_es": img.concept_es}
    return out


def state_for(db: Session, room: DuoRoom, seat: int, connected: set[int]) -> dict:
    """Vista personalizada de la sala: cada rol solo recibe lo que le corresponde ver."""
    db.refresh(room)
    me = next(p for p in room.players if p.seat == seat)
    rnd = current_round(db, room)
    view = None
    if rnd is not None:
        role = "describer" if rnd.describer_seat == seat else "guesser"
        view = {"number": rnd.number, "phase": rnd.phase, "role": role, "difficulty": rnd.difficulty}
        target = db.get(DuoImage, rnd.target_image_id)
        if role == "describer" and rnd.phase in ("describing", "guessing"):
            view["image"] = _image_out(target)  # la sigue viendo mientras el otro elige
            if rnd.phase == "describing":
                view["hints"] = hints(db, room.lang, target.concept_lemma)
        if rnd.phase in ("guessing", "done"):
            view["description"] = rnd.description
        if rnd.phase == "guessing" and role == "guesser":
            view["options"] = [_image_out(db.get(DuoImage, i)) for i in rnd.option_ids]
        if rnd.phase == "done":
            view["result"] = {"success": rnd.success, "chosen_image_id": rnd.chosen_image_id,
                              "target": _image_out(target, reveal_concept=True)}
    rounds_played = db.scalar(select(func.count()).where(
        DuoRound.room_id == room.id, DuoRound.phase == "done")) or 0
    return {
        "type": "state",
        "room": {"code": room.code, "lang": room.lang, "status": room.status, "score": room.score,
                 "rounds_played": rounds_played},
        "you": {"seat": seat, "consent": me.consent},
        "players": [{"seat": p.seat, "connected": p.seat in connected, "consent": p.consent}
                    for p in room.players],
        "round": view,
    }
