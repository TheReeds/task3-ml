"""Sesión anónima y envío de contribuciones (§7). La revisión (Taller) llega en la fase 3."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status
from sqlalchemy import select

from app.api.deps import DB, CurrentContributor, hash_token
from app.models import Alignment, Contribution, Contributor, Entry, Lexeme, Translation
from app.schemas import (
    AnonymousSession,
    ContributionIn,
    ContributionOut,
    ContributorOut,
    GlossFix,
    NewLemma,
    TranscriptionFix,
    TranslationFix,
)
from app.services.corpus import is_current

router = APIRouter()


@router.post("/auth/anonymous", response_model=AnonymousSession, status_code=201, tags=["auth"])
def create_anonymous_session(db: DB):
    """Contribuir no exige registro (§9.2): se emite un token opaco; solo se guarda su hash."""
    token = secrets.token_urlsafe(32)
    contributor = Contributor(token_hash=hash_token(token), reliability=0.5)
    db.add(contributor)
    db.commit()
    return AnonymousSession(contributor_id=contributor.id, token=token, reliability=contributor.reliability)


@router.get("/auth/me", response_model=ContributorOut, tags=["auth"])
def read_me(contributor: CurrentContributor):
    return contributor


def _current_or_404(db: DB, model, obj_id: int, label: str):
    obj = db.scalars(select(model).where(model.id == obj_id, is_current(model))).first()
    if obj is None:
        raise HTTPException(404, f"{label} no encontrada o ya sustituida por una versión más reciente")
    return obj


def _build(db: DB, body: ContributionIn) -> dict:
    """Valida el destino y normaliza la contribución a (lang, type, target, payload)."""
    match body:
        case TranscriptionFix():
            entry = _current_or_404(db, Entry, body.entry_id, "Entrada")
            original = db.scalars(
                select(Alignment).where(Alignment.entry_id == entry.id, Alignment.position == body.position)
            ).first()
            if original is None:
                raise HTTPException(422, "La entrada no tiene un token en esa posición")
            if original.token == body.token:
                raise HTTPException(422, "La corrección es idéntica al token actual")
            return dict(lang=entry.lang, target_type="entry", target_id=entry.id,
                        payload={"position": body.position, "original": original.token, "proposed": body.token})
        case TranslationFix():
            tr = _current_or_404(db, Translation, body.translation_id, "Traducción")
            if tr.text.strip() == body.text.strip():
                raise HTTPException(422, "La traducción propuesta es idéntica a la actual")
            entry = db.get(Entry, tr.entry_id)
            return dict(lang=entry.lang, target_type="translation", target_id=tr.id,
                        payload={"original": tr.text, "proposed": body.text.strip()})
        case GlossFix():
            lex = _current_or_404(db, Lexeme, body.lexeme_id, "Lema")
            return dict(lang=lex.lang, target_type="lexeme", target_id=lex.id,
                        payload={"lemma": lex.lemma, "original": lex.gloss, "proposed": body.gloss.strip()})
        case NewLemma():
            lemma = body.lemma.strip().lower()
            exists = db.scalars(
                select(Lexeme.id).where(Lexeme.lang == body.lang, Lexeme.lemma == lemma, is_current(Lexeme))
            ).first()
            if exists:
                raise HTTPException(409, "El lema ya existe en el corpus")
            return dict(lang=body.lang, target_type=None, target_id=None,
                        payload={"lemma": lemma, "gloss": body.gloss, "origin_module": body.origin_module})
    raise HTTPException(422, "Tipo de contribución no soportado")


@router.post("/contributions", response_model=ContributionOut, status_code=status.HTTP_201_CREATED,
             tags=["contributions"])
def create_contribution(
    db: DB,
    contributor: CurrentContributor,
    body: Annotated[ContributionIn, Body(discriminator="type")],
):
    """Registra una propuesta en estado `pending`. El dato original nunca se modifica (§7.1)."""
    fields = _build(db, body)
    duplicate = db.scalars(
        select(Contribution).where(
            Contribution.contributor_id == contributor.id,
            Contribution.type == body.type,
            Contribution.target_type == fields["target_type"],
            Contribution.target_id == fields["target_id"],
            Contribution.payload == fields["payload"],
            Contribution.status == "pending",
        )
    ).first()
    if duplicate:
        return duplicate
    contribution = Contribution(contributor_id=contributor.id, type=body.type, status="pending", **fields)
    db.add(contribution)
    db.commit()
    return contribution


@router.get("/contributions/mine", response_model=list[ContributionOut], tags=["contributions"])
def my_contributions(db: DB, contributor: CurrentContributor):
    return db.scalars(
        select(Contribution)
        .where(Contribution.contributor_id == contributor.id)
        .order_by(Contribution.created_at.desc())
    ).all()


