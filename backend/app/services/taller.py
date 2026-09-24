"""Módulo Taller (§6.7): bandeja de revisión, consenso, panel de impacto y exportación."""

import hashlib
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Alignment, Contribution, Contributor, Entry, GoldItem, Lexeme, Review, Translation
from app.services.apply import apply_contribution
from app.services.consensus import Vote, decide, reliability
from app.services.corpus import audio_url, get_current_translation
from app.services.versions import lineage_ids, resolve_current

REVIEWABLE = ("pending", "gold")


class ReviewError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status, self.detail = status, detail


# --- bandeja ---------------------------------------------------------------------


def _unreviewed_by(reviewer: Contributor):
    mine = select(Review.contribution_id).where(Review.reviewer_id == reviewer.id)
    return Contribution.id.not_in(mine)


def next_item(db: Session, reviewer: Contributor, lang: str) -> Contribution | None:
    """Siguiente contribución a revisar.

    Cada `gold_every` revisiones (empezando por la primera) se intercala un elemento de control
    no visto. Las contribuciones reales se ordenan por cercanía a resolverse y antigüedad.
    Nunca se ofrece una contribución propia ni una ya juzgada.
    """
    cfg = get_settings()
    done = db.scalar(select(func.count()).where(Review.reviewer_id == reviewer.id)) or 0
    if done % cfg.gold_every == 0:
        gold = db.scalars(
            select(Contribution)
            .where(Contribution.status == "gold", Contribution.lang == lang, _unreviewed_by(reviewer))
            .order_by(func.random())
            .limit(1)
        ).first()
        if gold:
            return gold

    n_reviews = (
        select(func.count()).where(Review.contribution_id == Contribution.id).scalar_subquery()
    )
    own = Contribution.contributor_id == reviewer.id
    return db.scalars(
        select(Contribution)
        .where(
            Contribution.status == "pending",
            Contribution.lang == lang,
            ~own | Contribution.contributor_id.is_(None),
            _unreviewed_by(reviewer),
        )
        .order_by(n_reviews.desc(), Contribution.created_at)
        .limit(1)
    ).first()


def build_context(db: Session, c: Contribution) -> dict:
    """Contexto necesario para evaluar la propuesta: audio, versión vigente y propuesta.

    Se construye desde el `payload` (no desde el estado actual) para que los elementos de
    control muestren exactamente la situación que se quiere evaluar.
    """
    if c.type == "transcription_fix":
        entry = db.get(Entry, c.target_id)
        tokens = db.scalars(
            select(Alignment).where(Alignment.entry_id == entry.id).order_by(Alignment.position)
        ).all()
        pos = c.payload["position"]
        shown = [c.payload["original"] if t.position == pos else t.token for t in tokens]
        tr = get_current_translation(db, entry.id)
        return {
            "entry_id": entry.id,
            "text": " ".join(shown),
            "audio_url": audio_url(entry),
            "position": pos,
            "segment_ms": [tokens[pos].start_ms, tokens[pos].end_ms] if pos < len(tokens) else None,
            "translation": tr.text if tr else None,
        }
    if c.type == "translation_fix":
        tr = db.get(Translation, c.target_id)
        entry = db.get(Entry, tr.entry_id)
        return {"entry_id": entry.id, "text": entry.text, "audio_url": audio_url(entry)}
    if c.type == "gloss_fix":
        lex = db.get(Lexeme, c.target_id)
        return {"lemma": lex.lemma, "examples": _examples(db, lex)}
    if c.type == "new_lemma":
        return {"lemma": c.payload["lemma"], "origin_module": c.payload.get("origin_module"),
                "vision_label": c.payload.get("label_es"),
                "existing_lemma": c.payload.get("existing_lexeme_id") is not None}
    if c.type == "new_sentence":
        return {"image_url": c.payload.get("image_url"), "concept_es": c.payload.get("concept_es"),
                "understood": c.payload.get("understood"), "origin_module": "duo"}
    if c.type == "audio_recording":
        lex = db.get(Lexeme, c.target_id)
        return {"lemma": lex.lemma, "gloss": lex.gloss, "duration_ms": c.payload.get("duration_ms")}
    return {}


def _examples(db: Session, lex: Lexeme, limit: int = 2) -> list[dict]:
    current = resolve_current(db, Lexeme, lex.id)
    ids = lineage_ids(db, Lexeme, current)
    entry_ids = db.scalars(
        select(Alignment.entry_id).where(Alignment.lexeme_id.in_(ids)).distinct().limit(limit)
    ).all()
    out = []
    for eid in entry_ids:
        tr = get_current_translation(db, eid)
        out.append({"text": db.get(Entry, eid).text, "translation": tr.text if tr else None})
    return out


def proposer_reliability(db: Session, c: Contribution) -> float | None:
    if c.contributor_id is None:
        # Elementos de control: se muestran como un aporte cualquiera de confiabilidad inicial
        return 0.5
    return db.get(Contributor, c.contributor_id).reliability


# --- juicio ----------------------------------------------------------------------


def submit_review(db: Session, reviewer: Contributor, contribution_id: int, verdict: str) -> Contribution:
    cfg = get_settings()
    c = db.scalars(
        select(Contribution).where(Contribution.id == contribution_id).with_for_update()
    ).first()
    if c is None:
        raise ReviewError(404, "Contribución no encontrada")
    if c.status not in REVIEWABLE:
        raise ReviewError(409, "La contribución ya fue resuelta")
    if c.contributor_id == reviewer.id:
        raise ReviewError(403, "No se pueden revisar las contribuciones propias")
    already = db.scalar(
        select(func.count()).where(Review.contribution_id == c.id, Review.reviewer_id == reviewer.id)
    )
    if already:
        raise ReviewError(409, "Ya emitiste un juicio sobre esta contribución")

    db.add(Review(contribution_id=c.id, reviewer_id=reviewer.id, verdict=verdict,
                  weight=reviewer.reliability))

    if c.status == "gold":
        # La incertidumbre no penaliza: declararla es preferible a un juicio infundado
        if verdict != "unsure":
            expected = db.scalars(select(GoldItem.expected_verdict).where(GoldItem.contribution_id == c.id)).one()
            reviewer.gold_seen += 1
            reviewer.gold_correct += int(verdict == expected)
            reviewer.reliability = reliability(
                reviewer.gold_seen, reviewer.gold_correct, reviewer.is_native_speaker, cfg
            )
        db.commit()
        return c

    db.flush()
    votes = [Vote(r.verdict, r.weight) for r in db.scalars(select(Review).where(Review.contribution_id == c.id))]
    status, score = decide(votes, cfg)
    c.score = score
    if status is not None:
        c.status = apply_contribution(db, c) if status == "accepted" else status
        c.resolved_at = datetime.now(UTC)
    db.commit()
    return c


# --- impacto y exportación ---------------------------------------------------------


def fleiss_kappa(items: list[list[str]], categories=("accept", "reject", "unsure")) -> float | None:
    """Kappa de Fleiss generalizado a número variable de revisores por ítem (n_i ≥ 2)."""
    items = [it for it in items if len(it) >= 2]
    if not items:
        return None
    totals = Counter()
    p_items = []
    for it in items:
        counts = Counter(it)
        totals.update(counts)
        n = len(it)
        p_items.append(sum(k * (k - 1) for k in counts.values()) / (n * (n - 1)))
    n_all = sum(totals.values())
    p_bar = sum(p_items) / len(p_items)
    p_e = sum((totals[c] / n_all) ** 2 for c in categories)
    if p_e == 1:
        return None
    return round((p_bar - p_e) / (1 - p_e), 4)


def impact(db: Session, lang: str) -> dict:
    real = Contribution.status != "gold"
    by_status = dict(db.execute(
        select(Contribution.status, func.count()).where(Contribution.lang == lang, real)
        .group_by(Contribution.status)
    ).all())
    accepted_by_type = dict(db.execute(
        select(Contribution.type, func.count())
        .where(Contribution.lang == lang, Contribution.status == "accepted").group_by(Contribution.type)
    ).all())
    review_rows = db.execute(
        select(Review.contribution_id, Review.verdict)
        .join(Contribution, Contribution.id == Review.contribution_id)
        .where(Contribution.lang == lang, real)
    ).all()
    grouped: dict[int, list[str]] = {}
    for cid, verdict in review_rows:
        grouped.setdefault(cid, []).append(verdict)
    contributors = db.scalar(
        select(func.count(func.distinct(Contribution.contributor_id))).where(Contribution.lang == lang, real)
    )
    reviewers = db.scalar(
        select(func.count(func.distinct(Review.reviewer_id)))
        .join(Contribution, Contribution.id == Review.contribution_id).where(Contribution.lang == lang)
    )
    return {
        "lang": lang,
        "contributions": {s: by_status.get(s, 0) for s in ("pending", "accepted", "rejected", "stale")},
        "accepted_by_type": accepted_by_type,
        "reviews": len(review_rows),
        "contributors": contributors,
        "reviewers": reviewers,
        "fleiss_kappa": fleiss_kappa(list(grouped.values())),
    }


def pseudonym(contributor_id) -> str | None:
    """Atribución anónima estable: no revela el id interno."""
    if contributor_id is None:
        return None
    return "anon-" + hashlib.sha256(str(contributor_id).encode()).hexdigest()[:10]


def export_rows(db: Session, lang: str) -> list[dict]:
    rows = db.execute(
        select(Contribution, func.count(Review.id))
        .outerjoin(Review, Review.contribution_id == Contribution.id)
        .where(Contribution.lang == lang, Contribution.status == "accepted")
        .group_by(Contribution.id)
        .order_by(Contribution.resolved_at)
    ).all()
    return [
        {
            "id": c.id,
            "lang": c.lang,
            "type": c.type,
            "target_type": c.target_type,
            "target_id": c.target_id,
            "original": c.payload.get("original"),
            "proposed": c.payload.get("proposed", c.payload.get("lemma")),
            "payload": c.payload,
            "consensus_score": round(c.score, 4) if c.score is not None else None,
            "reviews": n,
            "contributor": pseudonym(c.contributor_id),
            "created_at": c.created_at.isoformat(),
            "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        }
        for c, n in rows
    ]
