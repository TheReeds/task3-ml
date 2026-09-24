"""Consenso ponderado y estimación de confiabilidad (§7.3, §7.4). Funciones puras."""

from dataclasses import dataclass

from app.config import Settings

VERDICT_VALUE = {"accept": 1.0, "reject": 0.0}


@dataclass(frozen=True)
class Vote:
    verdict: str  # accept | reject | unsure
    weight: float


def weighted_score(votes: list[Vote]) -> float | None:
    """Σ(w·v) / Σw, descartando los juicios de incertidumbre."""
    firm = [v for v in votes if v.verdict in VERDICT_VALUE]
    total = sum(v.weight for v in firm)
    if not firm or total == 0:
        return None
    return sum(v.weight * VERDICT_VALUE[v.verdict] for v in firm) / total


def decide(votes: list[Vote], cfg: Settings) -> tuple[str | None, float | None]:
    """Devuelve (estado resuelto o None si sigue pendiente, puntaje)."""
    firm = [v for v in votes if v.verdict in VERDICT_VALUE]
    score = weighted_score(votes)
    if score is None or len(firm) < cfg.consensus_min_reviews:
        return None, score
    if sum(v.weight for v in firm) >= cfg.consensus_min_weight:
        if score >= cfg.consensus_accept:
            return "accepted", score
        if score <= cfg.consensus_reject:
            return "rejected", score
    if len(firm) >= cfg.consensus_max_reviews:
        return "rejected", score  # controversia persistente: no se modifica el corpus
    return None, score


def reliability(gold_seen: int, gold_correct: int, is_native: bool, cfg: Settings) -> float:
    """Media posterior Beta(1,1) del acierto sobre elementos de control, acotada.

    Parte de 0,5 sin evidencia. Solo los hablantes nativos con desempeño alto sostenido pueden
    superar `reliability_cap` y llegar a 1, lo que acelera la resolución de lo que revisan.
    """
    accuracy = (gold_correct + 1) / (gold_seen + 2)
    proven_native = (
        is_native and gold_seen >= cfg.native_min_gold and accuracy >= cfg.native_min_accuracy
    )
    ceiling = 1.0 if proven_native else cfg.reliability_cap
    return round(min(max(accuracy, 0.1), ceiling), 4)
