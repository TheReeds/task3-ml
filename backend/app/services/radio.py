"""Emisoras del módulo Radio (§6.3): filtros predefinidos sobre las entradas vigentes.

Una emisora se identifica con una cadena estable:
  aleatoria                      toda la colección, orden aleatorio
  facil | intermedia | dificil   tercios del índice de dificultad, en orden
  dominio:<valor>                por dominio temático (si el corpus lo trae)
  hablante:<valor>               por hablante (si el corpus lo trae)

Las emisoras ordenadas encadenan por id y vuelven al principio al terminar.
"""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Entry
from app.services.corpus import current_entries


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    description: str
    condition: ColumnElement[bool] | None
    shuffle: bool = False


DIFFICULTY_BANDS = {
    "facil": ("Fácil", "Frases cortas con vocabulario frecuente", 0.0, 1 / 3),
    "intermedia": ("Intermedia", "Dificultad media", 1 / 3, 2 / 3),
    "dificil": ("Difícil", "Frases largas con vocabulario poco frecuente", 2 / 3, 1.01),
}


def list_stations(db: Session, lang: str) -> list[Station]:
    stations = [Station("aleatoria", "Aleatoria", "Todo el corpus en orden aleatorio", None, True)]
    for sid, (name, desc, lo, hi) in DIFFICULTY_BANDS.items():
        stations.append(Station(sid, name, desc, Entry.difficulty.between(lo, hi - 1e-9)))
    base = current_entries(lang).subquery()
    for column, prefix, label in ((Entry.domain, "dominio", "Dominio"), (Entry.speaker, "hablante", "Hablante")):
        values = db.scalars(select(base.c[column.key]).distinct().where(base.c[column.key].is_not(None)))
        for v in sorted(values):
            stations.append(Station(f"{prefix}:{v}", f"{label}: {v}", f"Entradas con {column.key} = {v}", column == v))
    return stations


def get_station(db: Session, lang: str, station_id: str) -> Station | None:
    """Resuelve una emisora por id; las fijas no requieren consultar la base."""
    if station_id == "aleatoria":
        return Station("aleatoria", "Aleatoria", "Todo el corpus en orden aleatorio", None, True)
    if station_id in DIFFICULTY_BANDS:
        name, desc, lo, hi = DIFFICULTY_BANDS[station_id]
        return Station(station_id, name, desc, Entry.difficulty.between(lo, hi - 1e-9))
    prefix, _, value = station_id.partition(":")
    column = {"dominio": Entry.domain, "hablante": Entry.speaker}.get(prefix)
    if column is None or not value:
        return None
    exists = db.scalar(select(func.count()).select_from(
        current_entries(lang).where(column == value).subquery()))
    if not exists:
        return None
    label = "Dominio" if prefix == "dominio" else "Hablante"
    return Station(station_id, f"{label}: {value}", f"Entradas con {column.key} = {value}", column == value)


def count_entries(db: Session, lang: str, station: Station) -> int:
    stmt = current_entries(lang)
    if station.condition is not None:
        stmt = stmt.where(station.condition)
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def next_entry(
    db: Session, lang: str, station: Station, after: int | None, with_details: bool = False
) -> Entry | None:
    stmt = current_entries(lang)
    if with_details:  # tokens y traducciones en la misma ida a la base
        stmt = stmt.options(selectinload(Entry.alignments), selectinload(Entry.translations))
    if station.condition is not None:
        stmt = stmt.where(station.condition)
    if station.shuffle:
        if after is not None:
            stmt = stmt.where(Entry.id != after)
        return db.scalars(stmt.order_by(func.random()).limit(1)).first()
    ordered = stmt.order_by(Entry.id)
    if after is not None:
        following = db.scalars(ordered.where(Entry.id > after).limit(1)).first()
        if following:
            return following
    return db.scalars(ordered.limit(1)).first()
