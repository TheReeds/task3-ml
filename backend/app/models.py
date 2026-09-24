"""Esquema de datos (doc. técnico §8).

Tres grupos: núcleo del corpus, capa de contribución y juegos. Los registros del núcleo son
inmutables: una corrección aprobada inserta un registro nuevo con `supersedes_id` apuntando al
anterior, y las vistas `current_*` exponen solo la versión vigente (§8.3).
"""

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

TRANSLATION_ORIGINS = ("dataset", "model", "community")
AUDIO_ORIGINS = ("dataset", "synthetic", "community")
CONTRIBUTION_TYPES = (
    "transcription_fix",  # Radio
    "translation_fix",  # Radio
    "new_lemma",  # Radar, Lente
    "gloss_fix",  # Radar
    "audio_recording",  # Lente
    "new_sentence",  # Dúo
)
# stale: aceptada, pero el registro destino cambió antes de aplicarla (conflicto de versiones)
# withdrawn: el autor revocó su consentimiento (Dúo, §6.6); se excluye de revisión y exportación
CONTRIBUTION_STATUSES = ("pending", "accepted", "rejected", "stale", "gold", "withdrawn")
VERDICTS = ("accept", "reject", "unsure")
EMBEDDING_OWNERS = ("entry", "lexeme", "image")
VISION_METHODS = ("dictionary", "model", "community")


def _in(column: str, values: tuple[str, ...]) -> CheckConstraint:
    options = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({options})", name=f"ck_{column}_valid")


# ---------------------------------------------------------------------------
# Núcleo del corpus (§8.1)
# ---------------------------------------------------------------------------


class Entry(Base):
    """Enunciado del corpus en la lengua objetivo."""

    __tablename__ = "entries"
    __table_args__ = (_in("audio_origin", AUDIO_ORIGINS),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), index=True)
    text: Mapped[str] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(String(255))
    audio_origin: Mapped[str | None] = mapped_column(String(16))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    domain: Mapped[str | None] = mapped_column(String(64), index=True)
    speaker: Mapped[str | None] = mapped_column(String(64), index=True)
    difficulty: Mapped[float | None] = mapped_column(Float, index=True)
    source: Mapped[str] = mapped_column(String(64))
    source_ref: Mapped[str | None] = mapped_column(String(64))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("entries.id"), index=True)
    # Contribución aprobada que originó esta versión (atribución)
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("contributions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alignments: Mapped[list["Alignment"]] = relationship(
        back_populates="entry", order_by="Alignment.position"
    )
    translations: Mapped[list["Translation"]] = relationship(back_populates="entry")


class Alignment(Base):
    """Token mostrado de una entrada con sus marcas temporales (alineación forzada)."""

    __tablename__ = "alignments"
    __table_args__ = (UniqueConstraint("entry_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    token: Mapped[str] = mapped_column(String(128))
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    # False cuando el token no pudo alinearse (números, signos) y hereda tiempos vecinos
    aligned: Mapped[bool] = mapped_column(Boolean, default=True)
    lexeme_id: Mapped[int | None] = mapped_column(ForeignKey("lexemes.id"), index=True)

    entry: Mapped[Entry] = relationship(back_populates="alignments")
    lexeme: Mapped["Lexeme | None"] = relationship()


class Translation(Base):
    __tablename__ = "translations"
    __table_args__ = (_in("origin", TRANSLATION_ORIGINS),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"), index=True)
    lang: Mapped[str] = mapped_column(String(8), default="spa")
    text: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(16))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("translations.id"), index=True)
    # Contribución aprobada que originó esta versión (atribución)
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("contributions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entry: Mapped[Entry] = relationship(back_populates="translations")


class Lexeme(Base):
    """Lema del vocabulario con glosa y frecuencia en el corpus."""

    __tablename__ = "lexemes"
    __table_args__ = (_in("audio_origin", AUDIO_ORIGINS),)
    # Sin unicidad (lang, lemma): las versiones de un lema conviven; la vigente es única por lógica

    id: Mapped[int] = mapped_column(primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), index=True)
    lemma: Mapped[str] = mapped_column(String(128), index=True)
    gloss: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[int] = mapped_column(Integer, default=0)
    is_function_word: Mapped[bool] = mapped_column(Boolean, default=False)
    is_concrete: Mapped[bool] = mapped_column(Boolean, default=False)  # apto para Lente
    audio_path: Mapped[str | None] = mapped_column(String(255))  # pronunciación del lema
    audio_origin: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(64))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("lexemes.id"), index=True)
    # Contribución aprobada que originó esta versión (atribución)
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("contributions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Embedding(Base):
    """Vector de una entrada o de un lema, producido por un modelo concreto.

    La dimensión no se fija en el esquema: depende del modelo acordado en el contrato (§10.2).
    """

    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", "model"),
        _in("owner_type", EMBEDDING_OWNERS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(16))
    owner_id: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(64))
    vector: Mapped[list[float]] = mapped_column(Vector())


# ---------------------------------------------------------------------------
# Capa de contribución (§8.2)
# ---------------------------------------------------------------------------


class Contributor(Base):
    """Participante anónimo. Solo se guardan hashes de sus tokens y su confiabilidad."""

    __tablename__ = "contributors"
    __table_args__ = (CheckConstraint("reliability BETWEEN 0.1 AND 1.0", name="ck_reliability"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reliability: Mapped[float] = mapped_column(Float, default=0.5)
    is_native_speaker: Mapped[bool] = mapped_column(Boolean, default=False)
    gold_seen: Mapped[int] = mapped_column(Integer, default=0)
    gold_correct: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContributorToken(Base):
    """Token de acceso de un dispositivo. Una persona puede vincular varios (§9.2)."""

    __tablename__ = "contributor_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contributors.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkCode(Base):
    """Código de un solo uso y corta vida para vincular otro dispositivo a la misma identidad."""

    __tablename__ = "link_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contributors.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Contribution(Base):
    __tablename__ = "contributions"
    __table_args__ = (
        _in("type", CONTRIBUTION_TYPES),
        _in("status", CONTRIBUTION_STATUSES),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contributors.id"))
    lang: Mapped[str] = mapped_column(String(8))
    type: Mapped[str] = mapped_column(String(32), index=True)
    # Registro al que apunta (p. ej. "entry"/42 o "translation"/7); nulo para lemas nuevos
    target_type: Mapped[str | None] = mapped_column(String(16))
    target_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reviews: Mapped[list["Review"]] = relationship(back_populates="contribution")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("contribution_id", "reviewer_id"),
        _in("verdict", VERDICTS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contribution_id: Mapped[int] = mapped_column(ForeignKey("contributions.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contributors.id"))
    verdict: Mapped[str] = mapped_column(String(8))
    weight: Mapped[float] = mapped_column(Float)  # confiabilidad del revisor al momento de juzgar
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contribution: Mapped[Contribution] = relationship(back_populates="reviews")


class GoldItem(Base):
    """Contribución de control con veredicto conocido (estimación de confiabilidad, §7.4)."""

    __tablename__ = "gold_items"
    __table_args__ = (_in("expected_verdict", ("accept", "reject")),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contribution_id: Mapped[int] = mapped_column(ForeignKey("contributions.id"), unique=True)
    expected_verdict: Mapped[str] = mapped_column(String(8))


# ---------------------------------------------------------------------------
# Lente (§6.5)
# ---------------------------------------------------------------------------


class VisionLabel(Base):
    """Correspondencia entre una etiqueta del clasificador de visión y un lema de la lengua.

    Sin `lexeme_id`, la etiqueta es un vacío: la interfaz la presenta como oportunidad de aporte.
    Es un artefacto derivado del corpus, por eso se actualiza en sitio (con trazabilidad del método).
    """

    __tablename__ = "vision_labels"
    __table_args__ = (
        UniqueConstraint("label_set", "label", "lang"),
        _in("method", VISION_METHODS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    label_set: Mapped[str] = mapped_column(String(32))  # p. ej. coco-ssd
    label: Mapped[str] = mapped_column(String(64))  # etiqueta original del clasificador
    label_es: Mapped[str] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(8))
    lexeme_id: Mapped[int | None] = mapped_column(ForeignKey("lexemes.id"))
    method: Mapped[str | None] = mapped_column(String(16))
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("contributions.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Juegos
# ---------------------------------------------------------------------------


class RadarPuzzle(Base):
    """Palabra secreta del día por lengua (Radar, §6.4)."""

    __tablename__ = "radar_puzzles"
    __table_args__ = (UniqueConstraint("lang", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lang: Mapped[str] = mapped_column(String(8))
    day: Mapped[date] = mapped_column(Date)
    lexeme_id: Mapped[int] = mapped_column(ForeignKey("lexemes.id"))
    model: Mapped[str] = mapped_column(String(64))
    # Ranking precalculado {lexeme_id: percentil} sobre todo el vocabulario elegible
    ranking: Mapped[dict] = mapped_column(JSONB)


# ---------------------------------------------------------------------------
# Dúo (§6.6)
# ---------------------------------------------------------------------------

DUO_ROOM_STATUSES = ("waiting", "ready", "closed")
DUO_ROUND_PHASES = ("describing", "guessing", "done")


class DuoImage(Base):
    """Imagen del catálogo de Dúo. Se vincula al concepto por lema (texto), no por id, para que
    re-ingerir el corpus no invalide el catálogo."""

    __tablename__ = "duo_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), index=True)
    concept_lemma: Mapped[str] = mapped_column(String(128), index=True)
    concept_es: Mapped[str] = mapped_column(String(64))
    file_path: Mapped[str] = mapped_column(String(255))  # relativo a MEDIA_DIR
    source_url: Mapped[str] = mapped_column(String(512))
    author: Mapped[str | None] = mapped_column(String(255))
    license: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DuoRoom(Base):
    __tablename__ = "duo_rooms"
    __table_args__ = (_in("status", DUO_ROOM_STATUSES),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    lang: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="waiting")
    score: Mapped[int] = mapped_column(Integer, default=0)  # aciertos compartidos
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    players: Mapped[list["DuoPlayer"]] = relationship(order_by="DuoPlayer.seat")


class DuoPlayer(Base):
    __tablename__ = "duo_players"
    __table_args__ = (UniqueConstraint("room_id", "seat"), UniqueConstraint("room_id", "contributor_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("duo_rooms.id", ondelete="CASCADE"))
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contributors.id"))
    seat: Mapped[int] = mapped_column(Integer)  # 0 = creador, 1 = invitado
    # Consentimiento explícito, informado y revocable para capturar sus descripciones (§14)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DuoRound(Base):
    __tablename__ = "duo_rounds"
    __table_args__ = (UniqueConstraint("room_id", "number"), _in("phase", DUO_ROUND_PHASES))

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("duo_rooms.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    describer_seat: Mapped[int] = mapped_column(Integer)
    target_image_id: Mapped[int] = mapped_column(ForeignKey("duo_images.id"))
    option_ids: Mapped[list] = mapped_column(JSONB)  # 4 imágenes en el orden mostrado
    difficulty: Mapped[float] = mapped_column(Float)  # banda de similitud de los distractores
    phase: Mapped[str] = mapped_column(String(16), default="describing")
    description: Mapped[str | None] = mapped_column(Text)
    chosen_image_id: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool | None] = mapped_column(Boolean)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)  # el descriptor pasó la imagen
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("contributions.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Radio: temas automáticos (tabla 7: agrupamiento cuando el corpus no trae dominios)
# ---------------------------------------------------------------------------


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("lang", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lang: Mapped[str] = mapped_column(String(8))
    slug: Mapped[str] = mapped_column(String(64))  # valor guardado en entries.domain
    name: Mapped[str] = mapped_column(String(64))
    keywords: Mapped[list] = mapped_column(JSONB)
    method: Mapped[str] = mapped_column(String(32))  # "clustering" | "corpus"


# ---------------------------------------------------------------------------
# Instrumentación (§12): eventos anónimos de uso
# ---------------------------------------------------------------------------


class Event(Base):
    """Evento de uso. Sin IP ni datos personales: un id de dispositivo aleatorio del cliente."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    device_id: Mapped[str | None] = mapped_column(String(64), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(64), index=True)
    module: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(8))  # client | server
    props: Mapped[dict] = mapped_column(JSONB, default=dict)
