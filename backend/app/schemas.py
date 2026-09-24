import uuid
from datetime import datetime
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
    audio_url: str | None
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
