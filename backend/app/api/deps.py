from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Contributor
from app.services.auth import contributor_by_token

DB = Annotated[Session, Depends(get_db)]


def current_contributor(db: DB, authorization: Annotated[str | None, Header()] = None) -> Contributor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token anónimo (POST /auth/anonymous)")
    contributor = contributor_by_token(db, authorization[7:].strip())
    if contributor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token no reconocido")
    return contributor


CurrentContributor = Annotated[Contributor, Depends(current_contributor)]
