"""Búsqueda en el vocabulario: por lema (con formas flexionadas) o por glosa en español."""

import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lexeme
from app.nlp.quechua import lemmatize, normalize, tokenize
from app.services.corpus import is_current


def fold(text: str) -> str:
    """Minúsculas sin tildes (conserva la ñ) para comparar glosas en español."""
    t = unicodedata.normalize("NFD", text.lower().replace("ñ", "\0"))
    return "".join(c for c in t if not unicodedata.combining(c)).replace("\0", "ñ")


def search_lexemes(db: Session, lang: str, q: str, limit: int = 20,
                   concrete_only: bool = False) -> list[Lexeme]:
    """Orden: lema exacto, forma flexionada de un lema, prefijo de lema, palabra de la glosa,
    subcadena de la glosa; a igual relevancia, más frecuente primero."""
    stmt = select(Lexeme).where(Lexeme.lang == lang, is_current(Lexeme))
    if concrete_only:
        stmt = stmt.where(Lexeme.is_concrete)
    lexemes = db.scalars(stmt).all()
    words = tokenize(q)
    form = normalize(words[0]) if len(words) == 1 else normalize(q.strip())
    by_lemma = {lx.lemma: lx for lx in lexemes}
    root = lemmatize(form, by_lemma) if form else None
    query_es = fold(q.strip())

    def score(lx: Lexeme) -> int | None:
        if lx.lemma == form:
            return 0
        if lx.lemma == root:
            return 1
        if form and lx.lemma.startswith(form):
            return 2
        gloss = fold(lx.gloss or "")
        if query_es and query_es in {w.strip(" .,;()") for w in gloss.split()}:
            return 3
        if len(query_es) >= 3 and query_es in gloss:
            return 4
        return None

    ranked = [(s, -lx.frequency, lx.lemma, lx) for lx in lexemes if (s := score(lx)) is not None]
    ranked.sort(key=lambda r: r[:3])
    return [r[3] for r in ranked[:limit]]
