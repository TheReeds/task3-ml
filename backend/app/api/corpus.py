"""Lectura del corpus: módulo Radio, entradas y léxico."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DB
from app.config import get_settings
from app.models import Alignment, Entry, Lexeme
from app.schemas import (
    EntryOut,
    EntryVersion,
    ExampleOut,
    LexemeDetail,
    LexemeOut,
    StationOut,
    TokenOut,
    TranslationOut,
)
from app.services import radio
from app.services.corpus import audio_url, get_current_translation, get_entry, is_current

router = APIRouter()

Lang = Query(default=None, description="Código ISO 639-3; por defecto el de la configuración")


def _lang(lang: str | None) -> str:
    return lang or get_settings().default_lang


def entry_out(db: DB, entry: Entry) -> EntryOut:
    translation = get_current_translation(db, entry.id)
    return EntryOut(
        id=entry.id,
        lang=entry.lang,
        text=entry.text,
        audio_url=audio_url(entry),
        audio_origin=entry.audio_origin,
        duration_ms=entry.duration_ms,
        domain=entry.domain,
        speaker=entry.speaker,
        difficulty=entry.difficulty,
        source=entry.source,
        supersedes_id=entry.supersedes_id,
        translation=TranslationOut.model_validate(translation) if translation else None,
        tokens=[TokenOut.model_validate(a) for a in entry.alignments],
    )


@router.get("/radio/stations", response_model=list[StationOut], tags=["radio"])
def list_stations(db: DB, lang: str | None = Lang):
    lang = _lang(lang)
    return [
        StationOut(id=s.id, name=s.name, description=s.description, entries=radio.count_entries(db, lang, s))
        for s in radio.list_stations(db, lang)
    ]


@router.get("/radio/stations/{station_id}/next", response_model=EntryOut, tags=["radio"])
def next_in_station(
    station_id: str,
    db: DB,
    after: int | None = Query(default=None, description="Id de la entrada que acaba de sonar"),
    lang: str | None = Lang,
):
    lang = _lang(lang)
    station = radio.get_station(db, lang, station_id)
    if station is None:
        raise HTTPException(404, f"Emisora desconocida: {station_id}")
    entry = radio.next_entry(db, lang, station, after)
    if entry is None:
        raise HTTPException(404, "La emisora no tiene entradas")
    return entry_out(db, get_entry(db, entry.id))


@router.get("/entries/{entry_id}", response_model=EntryOut, tags=["corpus"])
def read_entry(entry_id: int, db: DB):
    entry = get_entry(db, entry_id)
    if entry is None:
        raise HTTPException(404, "Entrada no encontrada")
    return entry_out(db, entry)


@router.get("/entries/{entry_id}/history", response_model=list[EntryVersion], tags=["corpus"])
def entry_history(entry_id: int, db: DB):
    """Cadena de versiones, de la más reciente a la original (trazabilidad, §8.3)."""
    entry = db.get(Entry, entry_id)
    if entry is None:
        raise HTTPException(404, "Entrada no encontrada")
    # avanzar hasta la versión vigente
    while newer := db.scalars(select(Entry).where(Entry.supersedes_id == entry.id)).first():
        entry = newer
    chain = [entry]
    while chain[-1].supersedes_id is not None:
        chain.append(db.get(Entry, chain[-1].supersedes_id))
    return chain


@router.get("/lexemes/{lexeme_id}", response_model=LexemeDetail, tags=["corpus"])
def read_lexeme(lexeme_id: int, db: DB, examples: int = Query(default=3, ge=0, le=20)):
    """Panel de palabra de Radio: lema, glosa, frecuencia y ejemplos del corpus."""
    lexeme = db.get(Lexeme, lexeme_id)
    if lexeme is None:
        raise HTTPException(404, "Lema no encontrado")
    entry_ids = db.scalars(
        select(Alignment.entry_id)
        .join(Entry, Entry.id == Alignment.entry_id)
        .where(Alignment.lexeme_id == lexeme_id, is_current(Entry))
        .distinct()
        .limit(examples)
    ).all()
    out = []
    for eid in entry_ids:
        entry = db.get(Entry, eid)
        tr = get_current_translation(db, eid)
        out.append(ExampleOut(entry_id=eid, text=entry.text, translation=tr.text if tr else None))
    return LexemeDetail(**LexemeOut.model_validate(lexeme).model_dump(), examples=out)
