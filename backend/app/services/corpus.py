"""Consultas sobre la versión vigente del núcleo del corpus (§8.3)."""

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.config import get_settings
from app.models import Entry, Lexeme, Translation

# Prioridad de origen cuando una entrada tiene varias traducciones vigentes
ORIGIN_PRIORITY = {"community": 0, "dataset": 1, "model": 2}


def is_current(model):
    """Condición SQL: ningún otro registro sustituye a este."""
    newer = aliased(model)
    return ~exists().where(newer.supersedes_id == model.id)


def current_entries(lang: str):
    return select(Entry).where(Entry.lang == lang, is_current(Entry))


def get_entry(db: Session, entry_id: int) -> Entry | None:
    stmt = (
        select(Entry)
        .where(Entry.id == entry_id)
        .options(selectinload(Entry.alignments), selectinload(Entry.translations))
    )
    return db.scalars(stmt).first()


def get_current_translation(db: Session, entry_id: int) -> Translation | None:
    rows = db.scalars(
        select(Translation).where(Translation.entry_id == entry_id, is_current(Translation))
    ).all()
    return min(rows, key=lambda t: ORIGIN_PRIORITY[t.origin], default=None)


def entry_is_current(db: Session, entry_id: int) -> bool:
    return db.scalar(select(is_current(Entry)).where(Entry.id == entry_id)) or False


def audio_url(entry: Entry) -> str | None:
    return f"{get_settings().media_url}/{entry.audio_path}" if entry.audio_path else None


def get_lexeme(db: Session, lexeme_id: int) -> Lexeme | None:
    return db.get(Lexeme, lexeme_id)
