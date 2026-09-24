"""Módulo Lente: correspondencia etiqueta de visión → lema.

La clasificación ocurre en el navegador (TensorFlow.js) y ninguna imagen llega al servidor
(§6.5, requisito de privacidad). El cliente descarga esta tabla una vez y la consulta localmente.
"""

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DB
from app.config import get_settings
from app.models import Lexeme, VisionLabel
from app.schemas import LenteLabels, VisionLabelOut
from app.services.corpus import media_url
from app.services.versions import resolve_current

router = APIRouter(prefix="/lente", tags=["lente"])


@router.get("/labels", response_model=LenteLabels)
def labels(
    db: DB,
    lang: str | None = None,
    label_set: str = "coco-ssd",
    gaps_only: bool = Query(False, description="Solo etiquetas sin lema (oportunidades de aporte)"),
):
    lang = lang or get_settings().default_lang
    rows = db.scalars(
        select(VisionLabel).where(VisionLabel.lang == lang, VisionLabel.label_set == label_set)
        .order_by(VisionLabel.label)
    ).all()
    out = []
    for r in rows:
        lex = resolve_current(db, Lexeme, r.lexeme_id) if r.lexeme_id else None
        out.append(VisionLabelOut(
            label=r.label, label_es=r.label_es, lexeme_id=lex.id if lex else None,
            lemma=lex.lemma if lex else None, gloss=lex.gloss if lex else None,
            audio_url=media_url(lex.audio_path) if lex else None, method=r.method,
        ))
    mapped = sum(o.lexeme_id is not None for o in out)
    if gaps_only:
        out = [o for o in out if o.lexeme_id is None]
    return LenteLabels(label_set=label_set, lang=lang, mapped=mapped, total=len(rows), labels=out)
