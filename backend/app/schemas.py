import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- corpus -------------------------------------------------------------------


class TokenOut(ORM):
    position: int
    token: str
    start_ms: int | None
    end_ms: int | None
    aligned: bool
    lexeme_id: int | None


class TranslationOut(ORM):
    id: int
    lang: str
    text: str
    origin: str


class EntryOut(ORM):
    id: int
    lang: str
    text: str
    audio_url: str | None = Field(description="Ogg/Opus")
    audio_url_m4a: str | None = Field(default=None, description="Copia AAC para navegadores sin Opus")
    audio_origin: str | None
    duration_ms: int | None
    domain: str | None
    speaker: str | None
    difficulty: float | None
    source: str
    supersedes_id: int | None
    translation: TranslationOut | None
    tokens: list[TokenOut]


class EntryVersion(ORM):
    id: int
    text: str
    supersedes_id: int | None
    created_at: datetime


class StationOut(BaseModel):
    id: str
    name: str
    description: str
    entries: int


class LexemeOut(ORM):
    id: int
    lang: str
    lemma: str
    gloss: str | None
    frequency: int
    is_function_word: bool
    is_concrete: bool
    audio_url: str | None = None
    audio_url_m4a: str | None = None
    audio_origin: str | None = None


class LexemeDetail(LexemeOut):
    examples: list["ExampleOut"]


class ExampleOut(BaseModel):
    entry_id: int
    text: str
    translation: str | None


# --- contribución -------------------------------------------------------------


class AnonymousSession(BaseModel):
    contributor_id: uuid.UUID
    token: str = Field(description="Enviar como `Authorization: Bearer <token>`")
    reliability: float


class LinkCodeOut(BaseModel):
    code: str = Field(description="8 caracteres; mostrar para dictar o copiar en el otro dispositivo")
    expires_at: datetime


class LinkCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class ContributorOut(ORM):
    id: uuid.UUID
    reliability: float
    is_native_speaker: bool


class TranscriptionFix(BaseModel):
    type: Literal["transcription_fix"]
    entry_id: int
    position: int = Field(ge=0, description="Posición del token corregido")
    token: str = Field(min_length=1, max_length=128)


class TranslationFix(BaseModel):
    type: Literal["translation_fix"]
    translation_id: int
    text: str = Field(min_length=1, max_length=2000)


class NewLemma(BaseModel):
    type: Literal["new_lemma"]
    lang: str = "quy"
    lemma: str = Field(min_length=1, max_length=128)
    gloss: str | None = Field(default=None, max_length=500)
    origin_module: Literal["radar", "lente"] = "radar"
    # Desde Lente: etiqueta del clasificador que quedó sin lema (vacío)
    label_set: str | None = None
    vision_label: str | None = None


class GlossFix(BaseModel):
    type: Literal["gloss_fix"]
    lexeme_id: int
    gloss: str = Field(min_length=1, max_length=500)


ContributionIn = TranscriptionFix | TranslationFix | NewLemma | GlossFix


class ContributionOut(ORM):
    id: int
    lang: str
    type: str
    target_type: str | None
    target_id: int | None
    payload: dict
    status: str
    score: float | None
    created_at: datetime


# --- Taller ---------------------------------------------------------------------


class ContributorUpdate(BaseModel):
    is_native_speaker: bool = Field(description="Autodeclaración; solo pesa con desempeño probado")


class ReviewItem(BaseModel):
    contribution_id: int
    type: str
    lang: str
    original: str | None
    proposed: str | None
    context: dict
    proposer_reliability: float | None = Field(description="La identidad del proponente se oculta")


class ReviewIn(BaseModel):
    contribution_id: int
    verdict: Literal["accept", "reject", "unsure"]


class ReviewResult(BaseModel):
    contribution_id: int
    recorded: bool = True
    status: str = Field(description="`pending` mientras no haya consenso")


class ImpactOut(BaseModel):
    lang: str
    contributions: dict[str, int]
    accepted_by_type: dict[str, int]
    reviews: int
    contributors: int
    reviewers: int
    fleiss_kappa: float | None


# --- Radar ------------------------------------------------------------------------


class RadarToday(BaseModel):
    puzzle_id: int
    lang: str
    day: date
    letters: int
    vocabulary_size: int
    hints: dict[str, float] = Field(description="Similitud del vecino más cercano, del 10.º y del 100.º")


class RadarGuessIn(BaseModel):
    word: str = Field(min_length=1, max_length=64)
    puzzle_id: int | None = Field(default=None, description="Por defecto, el puzzle de hoy")
    lang: str | None = None


class RadarGuessOut(BaseModel):
    word: str
    known: bool
    lemma: str | None = None
    gloss: str | None = None
    lexeme_id: int | None = None
    rank: int | None = None
    percentile: float | None = Field(default=None, description="Más próxima que este % del vocabulario")
    similarity: float | None = None
    solved: bool = False
    can_contribute: bool = False
    suggestion: dict | None = Field(default=None, description="Cuerpo listo para POST /contributions")


class RadarNeighbor(BaseModel):
    lemma: str
    gloss: str | None
    rank: int
    percentile: float
    similarity: float


class RadarAnswer(BaseModel):
    puzzle_id: int
    day: date
    lemma: str
    gloss: str | None
    lexeme_id: int
    neighbors: list[RadarNeighbor]


# --- Lente --------------------------------------------------------------------------


class VisionLabelOut(BaseModel):
    label: str
    label_es: str
    lexeme_id: int | None
    lemma: str | None
    gloss: str | None
    audio_url: str | None
    audio_url_m4a: str | None = None
    method: str | None = Field(description="dictionary | model | community; nulo si es un vacío")


class LenteLabels(BaseModel):
    label_set: str
    lang: str
    mapped: int
    total: int
    labels: list[VisionLabelOut]


# --- Instrumentación ------------------------------------------------------------------


class EventIn(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_.]{1,63}$", examples=["radio.first_play"])
    module: Literal["app", "radio", "radar", "lente", "duo", "taller"] | None = None
    props: dict = Field(default_factory=dict, description="Datos del evento (máx. 2 KB)")


class EventsIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=50)
