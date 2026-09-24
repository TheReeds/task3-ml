"""Navegación por cadenas de versiones (supersedes_id)."""

from sqlalchemy import select
from sqlalchemy.orm import Session


def resolve_current(db: Session, model, obj_id: int):
    """Sigue la cadena hacia adelante hasta la versión vigente del registro."""
    obj = db.get(model, obj_id)
    while obj is not None:
        newer = db.scalars(select(model).where(model.supersedes_id == obj.id)).first()
        if newer is None:
            return obj
        obj = newer
    return None


def lineage_ids(db: Session, model, current) -> list[int]:
    """Ids de la versión dada y de todas las que sustituye."""
    ids = [current.id]
    while current.supersedes_id is not None:
        current = db.get(model, current.supersedes_id)
        ids.append(current.id)
    return ids
