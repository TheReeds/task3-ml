"""Módulo Taller: revisión comunitaria, panel de impacto y exportación abierta."""

import csv
import io
import json
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import DB, ClientInfo, CurrentContributor
from app.config import get_settings
from app.schemas import ImpactOut, ReviewIn, ReviewItem, ReviewResult
from app.services import metrics, taller

router = APIRouter(prefix="/taller", tags=["taller"])

ContributionType = Literal["transcription_fix", "translation_fix", "new_lemma", "gloss_fix",
                           "audio_recording", "new_sentence"]

# Las cabeceras HTTP deben ser ASCII
LICENSE_NOTE = (
    "Contribuciones comunitarias aprobadas por consenso en Corpus Vivo. "
    "Atribucion: seudonimo anonimo del contribuyente."
)


@router.get("/next", response_model=ReviewItem, responses={204: {"description": "Nada que revisar"}})
def next_review(
    db: DB,
    reviewer: CurrentContributor,
    lang: str | None = None,
    type: Annotated[list[ContributionType] | None, Query(description="Filtrar por tipo (repetible)")] = None,
):
    c = taller.next_item(db, reviewer, lang or get_settings().default_lang, type)
    if c is None:
        return Response(status_code=204)
    return ReviewItem(
        contribution_id=c.id,
        type=c.type,
        lang=c.lang,
        original=c.payload.get("original"),
        proposed=c.payload.get("proposed", c.payload.get("gloss")),
        context=taller.build_context(db, c),
        proposer_reliability=taller.proposer_reliability(db, c),
    )


@router.post("/reviews", response_model=ReviewResult, status_code=201)
def post_review(body: ReviewIn, db: DB, reviewer: CurrentContributor, client: ClientInfo):
    try:
        c = taller.submit_review(db, reviewer, body.contribution_id, body.verdict)
    except taller.ReviewError as e:
        raise HTTPException(e.status, e.detail) from e
    metrics.record(db, "review.created", "taller", device_id=client.device_id,
                   session_id=client.session_id, contributor_id=reviewer.id,
                   props={"verdict": body.verdict})
    db.commit()
    # un elemento de control nunca revela que lo es
    return ReviewResult(contribution_id=c.id, status="pending" if c.status == "gold" else c.status)


@router.get("/impact", response_model=ImpactOut)
def impact(db: DB, lang: str | None = None, days: int = Query(default=30, ge=1, le=365)):
    """Totales, acuerdo entre revisores y serie diaria (`timeline`) para gráficos."""
    return taller.impact(db, lang or get_settings().default_lang, days)


@router.get("/export")
def export(db: DB, lang: str | None = None, format: str = Query("jsonl", pattern="^(jsonl|csv)$")):
    """Descarga todas las contribuciones aprobadas en formato abierto, con atribución (§7.1)."""
    lang = lang or get_settings().default_lang
    rows = taller.export_rows(db, lang)
    filename = f"corpus-vivo-contribuciones-{lang}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"', "X-License-Note": LICENSE_NOTE}
    if format == "jsonl":
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        return Response(body, media_type="application/x-ndjson", headers=headers)
    buf = io.StringIO()
    fields = [k for k in (rows[0] if rows else {"id": 0}) if k != "payload"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)
