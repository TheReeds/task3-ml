from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Event

DEV = {"X-Device-Id": "device-aaaa-1111", "X-Session-Id": "session-0001"}


def test_events_require_device_id(client):
    body = {"events": [{"name": "radio.first_play", "module": "radio", "props": {"ms": 1800}}]}
    assert client.post("/events", json=body).status_code == 422
    assert client.post("/events", json=body, headers={"X-Device-Id": "x"}).status_code == 422
    assert client.post("/events", json=body, headers=DEV).json() == {"accepted": 1}


def test_event_validation(client):
    assert client.post("/events", json={"events": [{"name": "Bad Name"}]}, headers=DEV).status_code == 422
    assert client.post("/events", json={"events": []}, headers=DEV).status_code == 422
    big = {"events": [{"name": "app.x", "props": {"k": "v" * 3000}}]}
    assert client.post("/events", json=big, headers=DEV).status_code == 422


def test_metrics_summary(client, corpus):
    for ms in (1200, 2400, 3000):
        client.post("/events", headers=DEV,
                    json={"events": [{"name": "radio.first_play", "module": "radio", "props": {"ms": ms}}]})
    other = {"X-Device-Id": "device-bbbb-2222", "X-Session-Id": "session-0002"}
    client.post("/events", headers=other, json={"events": [{"name": "app.open", "module": "app"}]})
    # aporte desde el dispositivo DEV: evento de servidor con el mismo id
    token = client.post("/auth/anonymous", headers=DEV).json()["token"]
    r = client.post("/contributions", headers={**DEV, "Authorization": f"Bearer {token}"},
                    json={"type": "new_lemma", "lemma": "sara", "origin_module": "radar"})
    assert r.status_code == 201
    client.post("/radar/guess", headers=DEV, json={"word": "x"})  # sin puzzle: 503, no registra

    m = client.get("/metrics?days=7").json()
    assert m["time_to_first_audio_ms"] == {"median": 2400.0, "p90": 2880.0, "n": 3}
    assert m["active_devices"] == 2 and m["sessions"] == 2
    assert m["contributing_devices"] == 1 and m["contribution_rate"] == 0.5
    assert m["events_by_module"]["radar"] == 1  # contribution.created atribuido a radar
    assert m["daily_active_devices"][-1]["devices"] == 2


def test_retention_d7(client):
    def at(device, days_ago):
        client.post("/events", headers={"X-Device-Id": device}, json={"events": [{"name": "app.open"}]})
        with SessionLocal.begin() as db:
            db.execute(update(Event).where(Event.device_id == device, Event.ts > datetime.now(UTC)
                                           - timedelta(minutes=1))
                       .values(ts=datetime.now(UTC) - timedelta(days=days_ago)))

    at("device-returns-1", 20)
    at("device-returns-1", 11)  # volvió al día 9 tras su primer uso
    at("device-leaves-2", 18)
    at("device-too-new-3", 5)  # aún no cumple 14 días: fuera de la cohorte
    r = client.get("/metrics?days=30").json()["retention_d7"]
    assert r == {"cohort": 2, "returned": 1, "rate": 0.5}
