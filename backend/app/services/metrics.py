"""Instrumentación y métricas de evaluación (§12).

Los eventos se asocian a un id de dispositivo aleatorio que genera el cliente (cabecera
`X-Device-Id`); nunca se guarda IP, agente de usuario ni datos personales. Hay dos fuentes:
  client  eventos que solo el cliente conoce (p. ej. cuánto tardó en sonar la primera frase)
  server  acciones que el servidor ya procesa (aportes, revisiones, intentos, rondas)
"""

import re
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Event

EVENT_NAME = re.compile(r"^[a-z][a-z0-9_.]{1,63}$")
MODULES = ("app", "radio", "radar", "lente", "duo", "taller")
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def clean_id(value: str | None) -> str | None:
    return value if value and ID_PATTERN.match(value) else None


def record(db: Session, name: str, module: str | None, *, device_id: str | None = None,
           session_id: str | None = None, contributor_id=None, props: dict | None = None,
           source: str = "server") -> None:
    """Añade un evento a la sesión de base de datos actual (lo confirma quien llama)."""
    db.add(Event(name=name, module=module, device_id=clean_id(device_id),
                 session_id=clean_id(session_id), contributor_id=contributor_id,
                 props=props or {}, source=source))


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 1)


def summary(db: Session, days: int) -> dict:
    tz = get_settings().timezone
    params = {"days": days, "tz": tz}
    window = "ts >= now() - make_interval(days => :days)"
    local_day = "(ts AT TIME ZONE :tz)::date"

    # Tiempo hasta el primer dato útil: evento de cliente radio.first_play con props.ms
    ttfa = [float(r[0]) for r in db.execute(text(
        f"SELECT (props->>'ms')::float FROM events WHERE name = 'radio.first_play' "
        f"AND props ? 'ms' AND {window}"), params)]

    daily = db.execute(text(
        f"SELECT {local_day} AS d, count(DISTINCT device_id) FROM events "
        f"WHERE device_id IS NOT NULL AND {window} GROUP BY d ORDER BY d"), params).all()

    active, sessions = db.execute(text(
        f"SELECT count(DISTINCT device_id), count(DISTINCT session_id) FROM events "
        f"WHERE device_id IS NOT NULL AND {window}"), params).one()

    contributing = db.scalar(text(
        f"SELECT count(DISTINCT device_id) FROM events WHERE name = 'contribution.created' "
        f"AND device_id IS NOT NULL AND {window}"), params)

    # Retención a 7 días: de los dispositivos cuyo primer uso fue hace ≥ 14 días (y dentro de
    # la ventana), fracción que volvió entre el día 7 y el 13 después de ese primer uso.
    retention = db.execute(text(
        f"""WITH first AS (
              SELECT device_id, min({local_day}) AS d0 FROM events
              WHERE device_id IS NOT NULL GROUP BY device_id),
            cohort AS (
              SELECT * FROM first
              WHERE d0 <= (now() AT TIME ZONE :tz)::date - 14
                AND d0 >= (now() AT TIME ZONE :tz)::date - :days)
            SELECT count(*) AS n,
                   count(*) FILTER (WHERE EXISTS (
                     SELECT 1 FROM events e WHERE e.device_id = cohort.device_id
                       AND (e.ts AT TIME ZONE :tz)::date BETWEEN d0 + 7 AND d0 + 13)) AS back
            FROM cohort"""), params).one()

    by_module = dict(db.execute(text(
        f"SELECT coalesce(module, 'app'), count(*) FROM events WHERE {window} "
        f"GROUP BY 1 ORDER BY 2 DESC"), params).all())

    return {
        "days": days,
        "time_to_first_audio_ms": {"median": _percentile(ttfa, 0.5), "p90": _percentile(ttfa, 0.9),
                                   "n": len(ttfa)},
        "active_devices": active,
        "sessions": sessions,
        "sessions_per_device": round(sessions / active, 2) if active else None,
        "daily_active_devices": [{"day": d.isoformat() if isinstance(d, date) else str(d), "devices": n}
                                 for d, n in daily],
        "contributing_devices": contributing,
        "contribution_rate": round(contributing / active, 4) if active else None,
        "retention_d7": {"cohort": retention.n, "returned": retention.back,
                         "rate": round(retention.back / retention.n, 4) if retention.n else None},
        "events_by_module": by_module,
    }

