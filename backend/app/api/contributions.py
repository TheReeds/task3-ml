"""Sesión anónima y envío de contribuciones (§7). La revisión (Taller) llega en la fase 3."""

from typing import Annotated

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import DB, CurrentContributor
from app.config import get_settings
from app.models import Alignment, Contribution, Contributor, Entry, Lexeme, Translation, VisionLabel
from app.schemas import (
    AnonymousSession,
    ContributionIn,
    ContributionOut,
    ContributorOut,
    ContributorUpdate,
    GlossFix,
    LinkCodeIn,
    LinkCodeOut,
    NewLemma,
    TranscriptionFix,
    TranslationFix,
)
from app.services.consensus import reliability
from app.nlp.quechua import normalize
from app.services import audio, auth
from app.services.corpus import is_current, media_url

router = APIRouter()


@router.post("/auth/anonymous", response_model=AnonymousSession, status_code=201, tags=["auth"])
def create_anonymous_session(db: DB):
    """Contribuir no exige registro (§9.2): se emite un token opaco; solo se guarda su hash."""
    contributor, token = auth.create_contributor(db)
    return AnonymousSession(contributor_id=contributor.id, token=token, reliability=contributor.reliability)


@router.get("/auth/me", response_model=ContributorOut, tags=["auth"])
def read_me(contributor: CurrentContributor):
    return contributor


@router.post("/auth/link-code", response_model=LinkCodeOut, status_code=201, tags=["auth"])
def create_link_code(db: DB, contributor: CurrentContributor):
    """Código de un solo uso (10 min) para usar esta misma identidad en otro dispositivo."""
    code, expires = auth.create_link_code(db, contributor)
    return LinkCodeOut(code=code, expires_at=expires)


@router.post("/auth/link", response_model=AnonymousSession, tags=["auth"])
def redeem_link_code(body: LinkCodeIn, db: DB):
    """Canjea un código de vinculación: devuelve un token nuevo de la misma identidad."""
    result = auth.redeem_link_code(db, body.code)
    if result is None:
        raise HTTPException(400, "Código inválido, vencido o ya usado")
    contributor, token = result
    return AnonymousSession(contributor_id=contributor.id, token=token, reliability=contributor.reliability)


@router.patch("/auth/me", response_model=ContributorOut, tags=["auth"])
def update_me(body: ContributorUpdate, db: DB, contributor: CurrentContributor):
    """Declarar ser hablante nativo. El peso extra solo llega con buen desempeño en controles."""
    contributor.is_native_speaker = body.is_native_speaker
    contributor.reliability = reliability(
        contributor.gold_seen, contributor.gold_correct, body.is_native_speaker, get_settings()
    )
    db.commit()
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
            lemma = normalize(body.lemma.strip())
            exists = db.scalars(
                select(Lexeme.id).where(Lexeme.lang == body.lang, Lexeme.lemma == lemma, is_current(Lexeme))
            ).first()
            payload = {"lemma": lemma, "gloss": body.gloss, "origin_module": body.origin_module}
            if body.vision_label:
                label = db.scalars(select(VisionLabel).where(
                    VisionLabel.lang == body.lang, VisionLabel.label_set == (body.label_set or "coco-ssd"),
                    VisionLabel.label == body.vision_label)).first()
                if label is None:
                    raise HTTPException(422, "Etiqueta de visión desconocida")
                if label.lexeme_id is not None:
                    raise HTTPException(409, "Esa etiqueta ya tiene un lema asociado")
                payload |= {"label_set": label.label_set, "vision_label": label.label,
                            "label_es": label.label_es, "existing_lexeme_id": exists}
            elif exists:
                raise HTTPException(409, "El lema ya existe en el corpus")
            return dict(lang=body.lang, target_type=None, target_id=None, payload=payload)
    raise HTTPException(422, "Tipo de contribución no soportado")


@router.post("/contributions", response_model=ContributionOut, status_code=status.HTTP_201_CREATED,
             tags=["contributions"])
def create_contribution(
    db: DB,
    contributor: CurrentContributor,
    body: Annotated[ContributionIn, Body(discriminator="type")],
):
    """Registra una propuesta en estado `pending`. El dato original nunca se modifica (§7.1)."""
    return _save(db, contributor, body.type, _build(db, body))


def _save(db: DB, contributor: Contributor, type_: str, fields: dict) -> Contribution:
    duplicate = db.scalars(
        select(Contribution).where(
            Contribution.contributor_id == contributor.id,
            Contribution.type == type_,
            Contribution.target_type == fields["target_type"],
            Contribution.target_id == fields["target_id"],
            Contribution.payload == fields["payload"],
            Contribution.status == "pending",
        )
    ).first()
    if duplicate:
        return duplicate
    contribution = Contribution(contributor_id=contributor.id, type=type_, status="pending", **fields)
    db.add(contribution)
    db.commit()
    return contribution


@router.post("/contributions/audio", response_model=ContributionOut, status_code=status.HTTP_201_CREATED,
             tags=["contributions"])
def create_audio_contribution(
    db: DB,
    contributor: CurrentContributor,
    lexeme_id: Annotated[int, Form()],
    consent: Annotated[bool, Form(description="Consentimiento explícito para publicar la grabación")],
    file: Annotated[UploadFile, File(description="Pronunciación del lema (0,3–6 s, máx. 2 MB)")],
):
    """Grabación de la propia pronunciación de un lema (Lente). Queda pendiente de revisión."""
    if not consent:
        raise HTTPException(422, "Se requiere consentimiento explícito para aportar una grabación")
    lex = _current_or_404(db, Lexeme, lexeme_id, "Lema")
    try:
        path, duration = audio.store_recording(file.file.read(audio.MAX_BYTES + 1), lex.lang)
    except audio.AudioError as e:
        raise HTTPException(422, str(e)) from e
    fields = dict(lang=lex.lang, target_type="lexeme", target_id=lex.id, payload={
        "lemma": lex.lemma, "original": media_url(lex.audio_path), "audio_path": path,
        "proposed": media_url(path), "duration_ms": duration, "consent": True,
    })
    return _save(db, contributor, "audio_recording", fields)


@router.get("/contributions/mine", response_model=list[ContributionOut], tags=["contributions"])
def my_contributions(db: DB, contributor: CurrentContributor):
    return db.scalars(
        select(Contribution)
        .where(Contribution.contributor_id == contributor.id)
        .order_by(Contribution.created_at.desc())
    ).all()


