"""Módulo Radar (§6.4): juego diario de adivinanza por proximidad semántica.

- El vocabulario del juego son los lemas vigentes con vector en el modelo activo.
- El vocabulario del ranking son solo raíces; el intento del jugador se normaliza y se reduce a
  su raíz: "wasikunapi" cuenta como "wasi" y "maskaspa" como "maskay".
- La similitud se comunica como percentil sobre el vocabulario ("más próxima que el 94 %").
- La palabra del día se elige de forma determinista entre lemas de contenido frecuentes, y el
  ranking completo se calcula una sola vez por día y se guarda con el puzzle.
"""

import random
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.config import get_settings
from app.models import Embedding, Lexeme, RadarPuzzle
from app.nlp.quechua import lemmatize, normalize, tokenize
from app.services.corpus import is_current
from app.services.versions import resolve_current

EPOCH = date(2026, 1, 1)


class RadarError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status, self.detail = status, detail


def today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _vocabulary(db: Session, lang: str) -> tuple[list[Lexeme], np.ndarray, str]:
    model = get_adapter().embedding_model(lang)
    rows = db.execute(
        select(Lexeme, Embedding.vector)
        .join(Embedding, (Embedding.owner_type == "lexeme") & (Embedding.owner_id == Lexeme.id))
        .where(Lexeme.lang == lang, is_current(Lexeme), Embedding.model == model)
        .order_by(Lexeme.lemma)
    ).all()
    if not rows:
        raise RadarError(503, f"No hay vocabulario con vectores del modelo {model} para '{lang}'")
    lexemes = [r[0] for r in rows]
    mat = np.stack([np.asarray(r[1], dtype=np.float32) for r in rows])
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    return lexemes, mat, model


def roots_only(lexemes: list[Lexeme], mat: np.ndarray) -> tuple[list[Lexeme], np.ndarray]:
    """Descarta lemas del diccionario que son formas flexionadas o derivadas de otro lema.

    "maskaspa", "wasiy" o "rimani" figuran como entradas propias del diccionario; dejarlas en el
    ranking haría que proponer una forma conjugada de la palabra secreta no cuente como acierto.
    Fuera del ranking, el intento se reduce a su raíz ("maskaspa" → "maskay").
    """
    lemmas = {lx.lemma for lx in lexemes}
    keep = [i for i, lx in enumerate(lexemes) if lemmatize(lx.lemma, lemmas - {lx.lemma}) is None]
    return [lexemes[i] for i in keep], mat[keep]


def is_loanword(lx: Lexeme) -> bool:
    """Préstamo evidente: el lema coincide con su glosa en español ("animal" → "animal")."""
    return bool(lx.gloss) and normalize(lx.gloss.strip()) == lx.lemma


def eligible_targets(lexemes: list[Lexeme], min_frequency: int) -> list[Lexeme]:
    """Candidatas a palabra del día: raíces de contenido, no préstamos, con frecuencia suficiente."""
    return [
        lx for lx in lexemes
        if not lx.is_function_word and lx.frequency >= min_frequency and len(lx.lemma) >= 3
        and not is_loanword(lx)
    ]


def pick_target(candidates: list[Lexeme], lang: str, day: date) -> Lexeme:
    """Permutación fija por lengua recorrida día a día: no se repite hasta agotar la lista."""
    ordered = sorted(candidates, key=lambda lx: lx.lemma)
    random.Random(f"radar-{lang}").shuffle(ordered)
    return ordered[(day - EPOCH).days % len(ordered)]


def build_ranking(lexemes: list[Lexeme], mat: np.ndarray, target_idx: int) -> dict[str, list]:
    """{lema: [rango, percentil, similitud]}; el objetivo tiene rango 1 y percentil 100."""
    sims = mat @ mat[target_idx]
    sims[target_idx] = np.inf
    order = np.argsort(-sims)
    n = len(lexemes)
    ranking = {}
    for rank, i in enumerate(order, start=1):
        percentile = round(100 * (n - rank) / max(n - 1, 1), 1)
        sim = 1.0 if i == target_idx else round(float(sims[i]), 4)
        ranking[lexemes[i].lemma] = [rank, percentile, sim]
    return ranking


def get_or_create_puzzle(db: Session, lang: str, day: date) -> RadarPuzzle:
    existing = db.scalars(select(RadarPuzzle).where(RadarPuzzle.lang == lang, RadarPuzzle.day == day)).first()
    if existing:
        return existing
    lexemes, mat, model = _vocabulary(db, lang)
    lexemes, mat = roots_only(lexemes, mat)
    candidates = eligible_targets(lexemes, get_settings().radar_min_frequency)
    if not candidates:
        raise RadarError(503, "No hay lemas elegibles como palabra del día")
    target = pick_target(candidates, lang, day)
    idx = next(i for i, lx in enumerate(lexemes) if lx.id == target.id)
    puzzle = RadarPuzzle(lang=lang, day=day, lexeme_id=target.id, model=model,
                         ranking=build_ranking(lexemes, mat, idx))
    db.add(puzzle)
    try:
        db.commit()
    except IntegrityError:  # otra petición lo creó en paralelo
        db.rollback()
        return db.scalars(select(RadarPuzzle).where(RadarPuzzle.lang == lang, RadarPuzzle.day == day)).one()
    return puzzle


def target_lexeme(db: Session, puzzle: RadarPuzzle) -> Lexeme:
    # la glosa pudo corregirse después de crear el puzzle
    return resolve_current(db, Lexeme, puzzle.lexeme_id)


def hints(puzzle: RadarPuzzle) -> dict:
    """Similitud del vecino 1, 10 y 100 como referencia (estilo Semantle)."""
    by_rank = {v[0]: v[2] for v in puzzle.ranking.values()}
    return {f"top_{k}": by_rank.get(k + 1) for k in (1, 10, 100) if k + 1 in by_rank}


def guess(db: Session, puzzle: RadarPuzzle, word: str) -> dict:
    words = tokenize(word)
    if len(words) != 1:
        raise RadarError(422, "Propón una sola palabra")
    form = normalize(words[0])
    lemma = lemmatize(form, puzzle.ranking)
    if lemma is None:
        exists = db.scalars(
            select(Lexeme.id).where(Lexeme.lang == puzzle.lang, Lexeme.lemma == form, is_current(Lexeme))
        ).first()
        return {
            "word": word,
            "known": False,
            # §6.4: la palabra ausente no es un error sino una oportunidad de aporte léxico
            "can_contribute": exists is None,
            "suggestion": {"type": "new_lemma", "lang": puzzle.lang, "lemma": form, "origin_module": "radar"}
            if exists is None else None,
        }
    rank, percentile, similarity = puzzle.ranking[lemma]
    lex = db.scalars(
        select(Lexeme).where(Lexeme.lang == puzzle.lang, Lexeme.lemma == lemma, is_current(Lexeme))
    ).first()
    return {
        "word": word,
        "known": True,
        "lemma": lemma,
        "gloss": lex.gloss if lex else None,
        "lexeme_id": lex.id if lex else None,
        "rank": rank,
        "percentile": percentile,
        "similarity": similarity,
        "solved": rank == 1,
    }


def answer(db: Session, puzzle: RadarPuzzle, neighbors: int = 10) -> dict:
    target = target_lexeme(db, puzzle)
    top = sorted(puzzle.ranking.items(), key=lambda kv: kv[1][0])[1 : neighbors + 1]
    glosses = dict(db.execute(
        select(Lexeme.lemma, Lexeme.gloss)
        .where(Lexeme.lang == puzzle.lang, Lexeme.lemma.in_([k for k, _ in top]), is_current(Lexeme))
    ).all())
    return {
        "lemma": target.lemma,
        "gloss": target.gloss,
        "lexeme_id": target.id,
        "neighbors": [
            {"lemma": k, "gloss": glosses.get(k), "rank": v[0], "percentile": v[1], "similarity": v[2]}
            for k, v in top
        ],
    }
