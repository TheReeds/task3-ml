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


class Client:
    """Identificadores anónimos que el cliente envía en cabeceras (instrumentación, §12)."""

    def __init__(self, device_id: str | None, session_id: str | None, module: str | None) -> None:
        self.device_id, self.session_id, self.module = device_id, session_id, module


def client_info(
    x_device_id: Annotated[str | None, Header()] = None,
    x_session_id: Annotated[str | None, Header()] = None,
    x_module: Annotated[str | None, Header()] = None,
) -> Client:
    return Client(x_device_id, x_session_id, x_module)


ClientInfo = Annotated[Client, Depends(client_info)]
