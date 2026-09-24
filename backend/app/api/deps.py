import hashlib
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Contributor

DB = Annotated[Session, Depends(get_db)]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_contributor(db: DB, authorization: Annotated[str | None, Header()] = None) -> Contributor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token anónimo (POST /auth/anonymous)")
    contributor = db.scalars(
        select(Contributor).where(Contributor.token_hash == hash_token(authorization[7:].strip()))
    ).first()
    if contributor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token no reconocido")
    return contributor


CurrentContributor = Annotated[Contributor, Depends(current_contributor)]
