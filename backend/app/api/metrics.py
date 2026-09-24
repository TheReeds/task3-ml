"""Instrumentación de uso y métricas de evaluación (§12)."""

import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query

from app.api.deps import DB, ClientInfo
from app.schemas import EventsIn
from app.services import metrics
from app.services.auth import contributor_by_token

router = APIRouter(tags=["metrics"])


@router.post("/events", status_code=202)
def post_events(body: EventsIn, db: DB, client: ClientInfo,
                authorization: Annotated[str | None, Header()] = None):
    """Registra eventos del cliente. Requiere la cabecera `X-Device-Id` (id aleatorio del
    dispositivo, sin datos personales); `X-Session-Id` y `Authorization` son opcionales."""
    if metrics.clean_id(client.device_id) is None:
        raise HTTPException(422, "Falta X-Device-Id (8–64 caracteres alfanuméricos, - o _)")
    contributor = None
    if authorization and authorization.lower().startswith("bearer "):
        contributor = contributor_by_token(db, authorization[7:].strip())
    for ev in body.events:
        if len(json.dumps(ev.props)) > 2048:
            raise HTTPException(422, f"props de '{ev.name}' supera 2 KB")
        metrics.record(db, ev.name, ev.module, device_id=client.device_id,
                       session_id=client.session_id,
                       contributor_id=contributor.id if contributor else None,
                       props=ev.props, source="client")
    db.commit()
    return {"accepted": len(body.events)}


@router.get("/metrics")
def get_metrics(db: DB, days: int = Query(default=30, ge=1, le=365)):
    """Métricas agregadas: tiempo hasta la primera frase, dispositivos activos, sesiones,
    retención a 7 días y proporción de dispositivos que aportan."""
    return metrics.summary(db, days)
