"""Aplicación de contribuciones aceptadas al corpus (§7.1, §8.3).

Nunca se modifica un registro existente: cada corrección inserta una versión nueva que apunta a
la anterior (`supersedes_id`) y a la contribución que la originó (`contribution_id`).

Si el registro destino cambió desde que se propuso la contribución (otra corrección aprobada
antes), la propuesta se marca `stale` en lugar de pisar el cambio intermedio.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.models import Alignment, Contribution, Embedding, Entry, Lexeme, Translation
from app.nlp.quechua import lemmatize, normalize, tokenize
from app.services.corpus import is_current
from app.services.versions import resolve_current


def apply_contribution(db: Session, c: Contribution) -> str:
    """Aplica una contribución aceptada. Devuelve el estado final: `accepted` o `stale`."""
    handler = {
        "transcription_fix": _apply_transcription,
        "translation_fix": _apply_translation,
        "gloss_fix": _apply_gloss,
        "new_lemma": _apply_new_lemma,
    }.get(c.type)
    if handler is None:
        return "accepted"  # tipos sin efecto sobre el núcleo (audio, oraciones): se exportan
    return "accepted" if handler(db, c) else "stale"


def _embed(db: Session, owner_type: str, owner_id: int, text: str, lang: str) -> None:
    adapter = get_adapter()
    vec = adapter.embed([text], lang)[0]
    db.add(Embedding(owner_type=owner_type, owner_id=owner_id,
                     model=adapter.embedding_model(lang), vector=vec))


def _current_lemma_ids(db: Session, lang: str) -> dict[str, int]:
    rows = db.execute(select(Lexeme.lemma, Lexeme.id).where(Lexeme.lang == lang, is_current(Lexeme)))
    return dict(rows.all())


def _apply_transcription(db: Session, c: Contribution) -> bool:
    entry = resolve_current(db, Entry, c.target_id)
    pos, original, proposed = c.payload["position"], c.payload["original"], c.payload["proposed"]
    tokens = db.scalars(
        select(Alignment).where(Alignment.entry_id == entry.id).order_by(Alignment.position)
    ).all()
    if pos >= len(tokens) or tokens[pos].token != original:
        return False

    new_entry = Entry(
        lang=entry.lang,
        text=" ".join(proposed if t.position == pos else t.token for t in tokens),
        audio_path=entry.audio_path,
        audio_origin=entry.audio_origin,
        duration_ms=entry.duration_ms,
        domain=entry.domain,
        speaker=entry.speaker,
        difficulty=entry.difficulty,
        source=entry.source,
        source_ref=entry.source_ref,
        supersedes_id=entry.id,
        contribution_id=c.id,
    )
    db.add(new_entry)
    db.flush()

    lemma_ids = _current_lemma_ids(db, entry.lang)
    for t in tokens:
        lexeme_id = t.lexeme_id
        if t.position == pos:
            words = tokenize(proposed)
            lemma = lemmatize(normalize(words[0]), lemma_ids) if len(words) == 1 else None
            lexeme_id = lemma_ids.get(lemma) if lemma else None
        db.add(Alignment(
            entry_id=new_entry.id, position=t.position,
            token=proposed if t.position == pos else t.token,
            start_ms=t.start_ms, end_ms=t.end_ms, aligned=t.aligned, lexeme_id=lexeme_id,
        ))
    # Las traducciones vigentes acompañan a la nueva versión de la entrada
    for tr in db.scalars(
        select(Translation).where(Translation.entry_id == entry.id, is_current(Translation))
    ):
        db.add(Translation(entry_id=new_entry.id, lang=tr.lang, text=tr.text, origin=tr.origin,
                           supersedes_id=tr.id, contribution_id=tr.contribution_id))
    _embed(db, "entry", new_entry.id, new_entry.text, entry.lang)
    return True


def _apply_translation(db: Session, c: Contribution) -> bool:
    tr = resolve_current(db, Translation, c.target_id)
    if tr.text != c.payload["original"]:
        return False
    db.add(Translation(entry_id=tr.entry_id, lang=tr.lang, text=c.payload["proposed"],
                       origin="community", supersedes_id=tr.id, contribution_id=c.id))
    return True


def _apply_gloss(db: Session, c: Contribution) -> bool:
    lex = resolve_current(db, Lexeme, c.target_id)
    if lex.gloss != c.payload["original"]:
        return False
    new = Lexeme(lang=lex.lang, lemma=lex.lemma, gloss=c.payload["proposed"], frequency=lex.frequency,
                 is_function_word=lex.is_function_word, is_concrete=lex.is_concrete,
                 source=lex.source, supersedes_id=lex.id, contribution_id=c.id)
    db.add(new)
    db.flush()
    # mismo lema → mismos vectores
    for emb in db.scalars(select(Embedding).where(Embedding.owner_type == "lexeme",
                                                  Embedding.owner_id == lex.id)):
        db.add(Embedding(owner_type="lexeme", owner_id=new.id, model=emb.model, vector=emb.vector))
    return True


def _apply_new_lemma(db: Session, c: Contribution) -> bool:
    lemma = c.payload["lemma"]
    if lemma in _current_lemma_ids(db, c.lang):
        return False
    lex = Lexeme(lang=c.lang, lemma=lemma, gloss=c.payload.get("gloss"), frequency=0,
                 source="community", contribution_id=c.id)
    db.add(lex)
    db.flush()
    _embed(db, "lexeme", lex.id, lemma, c.lang)
    return True
