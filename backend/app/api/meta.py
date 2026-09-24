"""Metadatos del servicio: lenguas disponibles y qué módulos tienen datos en cada una."""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DB
from app.config import get_settings
from app.models import DuoImage, Entry, Lexeme, Topic, VisionLabel
from app.services.corpus import is_current

router = APIRouter(tags=["meta"])

LANGUAGE_NAMES = {
    "quy": {"name": "Quechua sureño (chanka)", "endonym": "Runasimi", "iso639_1": "qu"},
    "quz": {"name": "Quechua sureño (cusqueño)", "endonym": "Runasimi", "iso639_1": "qu"},
    "ayr": {"name": "Aimara central", "endonym": "Aymar aru", "iso639_1": "ay"},
}


def _counts(db, column, *where) -> dict[str, int]:
    return dict(db.execute(select(column, func.count()).where(*where).group_by(column)).all())


@router.get("/languages")
def languages(db: DB):
    """Lenguas con datos y disponibilidad por módulo. El frontend no debe fijar `quy`."""
    entries = _counts(db, Entry.lang, is_current(Entry))
    lexemes = _counts(db, Lexeme.lang, is_current(Lexeme))
    labels = _counts(db, VisionLabel.lang, VisionLabel.lexeme_id.is_not(None))
    images = _counts(db, DuoImage.lang, DuoImage.active)
    topics = _counts(db, Topic.lang)
    out = []
    for code in sorted(set(entries) | set(lexemes)):
        meta = LANGUAGE_NAMES.get(code, {"name": code, "endonym": None, "iso639_1": None})
        out.append({
            "code": code, **meta, "default": code == get_settings().default_lang,
            "counts": {"entries": entries.get(code, 0), "lexemes": lexemes.get(code, 0),
                       "vision_labels_mapped": labels.get(code, 0), "duo_images": images.get(code, 0),
                       "topics": topics.get(code, 0)},
            "modules": {"radio": entries.get(code, 0) > 0, "radar": lexemes.get(code, 0) > 0,
                        "lente": labels.get(code, 0) > 0, "duo": images.get(code, 0) >= 4,
                        "taller": True},
        })
    return out
