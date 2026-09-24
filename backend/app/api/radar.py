"""Módulo Radar: palabra secreta diaria por proximidad semántica."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DB, ClientInfo
from app.config import get_settings
from app.models import RadarPuzzle
from app.schemas import RadarAnswer, RadarArchiveItem, RadarGuessIn, RadarGuessOut, RadarToday
from app.services import metrics, radar

router = APIRouter(prefix="/radar", tags=["radar"])


def _puzzle(db: DB, puzzle_id: int | None, lang: str | None) -> RadarPuzzle:
    try:
        if puzzle_id is None:
            return radar.get_or_create_puzzle(db, lang or get_settings().default_lang, radar.today())
    except radar.RadarError as e:
        raise HTTPException(e.status, e.detail) from e
    puzzle = db.get(RadarPuzzle, puzzle_id)
    if puzzle is None or puzzle.day > radar.today():
        raise HTTPException(404, "Puzzle no encontrado")
    return puzzle


@router.get("/today", response_model=RadarToday)
def today(db: DB, lang: str | None = None):
    puzzle = _puzzle(db, None, lang)
    return RadarToday(
        puzzle_id=puzzle.id,
        lang=puzzle.lang,
        day=puzzle.day,
        letters=len(radar.target_lexeme(db, puzzle).lemma),
        vocabulary_size=len(puzzle.ranking),
        hints=radar.hints(puzzle),
    )


@router.get("/puzzles", response_model=list[RadarArchiveItem])
def archive(db: DB, lang: str | None = None, days: int = Query(default=7, ge=1, le=60)):
    """Archivo de los últimos días (el primero es hoy). Se juegan con `puzzle_id` en /radar/guess;
    la respuesta de los días pasados se consulta en /radar/puzzles/{id}/answer."""
    try:
        puzzles = radar.recent_puzzles(db, lang or get_settings().default_lang, days)
    except radar.RadarError as e:
        raise HTTPException(e.status, e.detail) from e
    today_ = radar.today()
    return [RadarArchiveItem(puzzle_id=p.id, day=p.day, letters=len(radar.target_lexeme(db, p).lemma),
                             is_today=p.day == today_) for p in puzzles]


@router.post("/guess", response_model=RadarGuessOut)
def guess(body: RadarGuessIn, db: DB, client: ClientInfo):
    puzzle = _puzzle(db, body.puzzle_id, body.lang)
    try:
        result = radar.guess(db, puzzle, body.word)
    except radar.RadarError as e:
        raise HTTPException(e.status, e.detail) from e
    metrics.record(db, "radar.guess", "radar", device_id=client.device_id,
                   session_id=client.session_id,
                   props={"puzzle_id": puzzle.id, "known": result["known"],
                          "solved": result.get("solved", False)})
    db.commit()
    return result


@router.get("/puzzles/{puzzle_id}/answer", response_model=RadarAnswer)
def reveal(puzzle_id: int, db: DB, give_up: bool = Query(False, description="Rendirse en el puzzle de hoy")):
    """Respuesta y vecinos más cercanos. Para el puzzle de hoy solo si el jugador se rinde."""
    puzzle = _puzzle(db, puzzle_id, None)
    if puzzle.day == radar.today() and not give_up:
        raise HTTPException(403, "El puzzle de hoy sigue en juego (use give_up=true para rendirse)")
    return RadarAnswer(puzzle_id=puzzle.id, day=puzzle.day, **radar.answer(db, puzzle))
