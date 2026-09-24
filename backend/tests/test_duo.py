import random

import numpy as np
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Contribution, Contributor, DuoImage, Embedding
from app.services import duo

CONCEPTS = ["allqu", "misi", "wasi", "yaku", "rumi", "sacha"]
ES = {"allqu": "perro", "misi": "gato", "wasi": "casa", "yaku": "agua", "rumi": "piedra", "sacha": "árbol"}


def unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def catalog():
    """Dos imágenes por concepto; los vectores ordenan la similitud con 'allqu' de forma conocida."""
    with SessionLocal.begin() as db:
        for k, lemma in enumerate(CONCEPTS):
            for j in range(2):
                img = DuoImage(lang="quy", concept_lemma=lemma, concept_es=ES[lemma],
                               file_path=f"duo/{lemma}-{j}.jpg", source_url="https://example.org",
                               author="test", license="CC0")
                db.add(img)
                db.flush()
                vec = unit([1.0, k * 0.8 + j * 0.05, 0, 0])  # k mayor = menos parecido a allqu
                db.add(Embedding(owner_type="image", owner_id=img.id, model=duo.CLIP_ID, vector=vec))


def tokens(client, n):
    return [client.post("/auth/anonymous").json()["token"] for _ in range(n)]


def auth(t):
    return {"Authorization": f"Bearer {t}"}


# --- unidades -------------------------------------------------------------------


def test_staircase_converges_to_target_success():
    # a p = 0,65 el paso esperado es nulo
    expected = duo.TARGET_SUCCESS * duo.STEP_UP - (1 - duo.TARGET_SUCCESS) * duo.STEP_DOWN
    assert abs(expected) < 1e-9
    assert duo.next_difficulty(None) == duo.INITIAL_DIFFICULTY


def test_distractors_follow_difficulty(catalog):
    with SessionLocal() as db:
        images, mat = duo._image_vectors(db, "quy")
    target = next(i for i, im in enumerate(images) if im.concept_lemma == "allqu")
    rng = random.Random(0)
    easy = {im.concept_lemma for im in duo.choose_distractors(images, mat, target, 0.0, rng)}
    hard = {im.concept_lemma for im in duo.choose_distractors(images, mat, target, 1.0, rng)}
    assert easy == {"yaku", "rumi", "sacha"}  # los menos parecidos
    assert hard == {"misi", "wasi", "yaku"}  # los más parecidos
    assert "allqu" not in easy | hard


# --- partida completa --------------------------------------------------------------


def drain(ws, n=1):
    msgs = [ws.receive_json() for _ in range(n)]
    return msgs[-1]


def test_full_game_over_websocket(client, catalog):
    ta, tb = tokens(client, 2)
    code = client.post("/duo/rooms", headers=auth(ta)).json()["code"]
    assert client.post(f"/duo/rooms/{code}/join", headers=auth(tb)).json()["seat"] == 1
    assert client.put(f"/duo/rooms/{code}/consent", headers=auth(ta), json={"consent": True}).status_code == 200

    with client.websocket_connect(f"/duo/ws/{code}?token={ta}") as wa:
        s = drain(wa)
        assert s["room"]["status"] == "ready" and s["you"] == {"seat": 0, "consent": True}
        with client.websocket_connect(f"/duo/ws/{code}?token={tb}") as wb:
            drain(wa), drain(wb)  # presencia

            wa.send_json({"action": "start_round"})
            sa, sb = drain(wa), drain(wb)
            assert sa["round"]["role"] == "describer" and "image" in sa["round"]
            assert sb["round"]["role"] == "guesser" and "image" not in sb["round"]
            assert "options" not in sb["round"]  # aún no hay descripción

            # el adivinador no puede describir; nombrar el concepto en español se rechaza
            wb.send_json({"action": "describe", "text": "hola"})
            assert wb.receive_json() == {"type": "error", "status": 403, "detail": "En esta ronda te toca adivinar"}
            with SessionLocal() as db:
                concept_es = db.get(DuoImage, sa["round"]["image"]["id"]).concept_es
            wa.send_json({"action": "describe", "text": f"kayqa {concept_es}"})
            assert wa.receive_json()["status"] == 422

            wa.send_json({"action": "describe", "text": "Kayqa hatun uywa"})
            sa, sb = drain(wa), drain(wb)
            options = sb["round"]["options"]
            assert len(options) == 4 and sb["round"]["description"] == "Kayqa hatun uywa"
            assert all("concept_es" not in o for o in options)  # sin pistas en las opciones

            wb.send_json({"action": "guess", "image_id": 999999})
            assert wb.receive_json()["status"] == 422
            wb.send_json({"action": "guess", "image_id": sa["round"]["image"]["id"]})
            sa, sb = drain(wa), drain(wb)
            assert sa["round"]["result"]["success"] is True and sa["room"]["score"] == 1
            assert sb["round"]["result"]["target"]["concept_es"] == concept_es

            # ronda 2: roles invertidos; B no dio consentimiento → no se captura su texto
            wb.send_json({"action": "start_round"})
            sa, sb = drain(wa), drain(wb)
            assert sb["round"]["role"] == "describer" and sa["round"]["difficulty"] > duo.INITIAL_DIFFICULTY
            wb.send_json({"action": "describe", "text": "Uchuy"})
            sa, sb = drain(wa), drain(wb)
            with SessionLocal() as db:
                target = duo.current_round(db, duo.get_room(db, code)).target_image_id
            wrong = next(o["id"] for o in sa["round"]["options"] if o["id"] != target)
            wa.send_json({"action": "guess", "image_id": wrong})
            sa, sb = drain(wa), drain(wb)
            assert sa["round"]["result"]["success"] is False and sa["room"]["score"] == 1

    with SessionLocal() as db:
        captured = db.scalars(select(Contribution).where(Contribution.type == "new_sentence")).all()
    assert [c.payload["proposed"] for c in captured] == ["Kayqa hatun uywa"]
    assert captured[0].payload["understood"] is True


def test_sentence_goes_to_taller_and_consent_revocation_withdraws_it(client, catalog):
    ta, tb, reviewer = tokens(client, 3)
    code = client.post("/duo/rooms", headers=auth(ta)).json()["code"]
    client.post(f"/duo/rooms/{code}/join", headers=auth(tb))
    client.put(f"/duo/rooms/{code}/consent", headers=auth(ta), json={"consent": True})
    with SessionLocal() as db:
        room = duo.get_room(db, code)
        rnd = duo.start_round(db, room, random.Random(1))
        a = next(p for p in room.players if p.seat == 0).contributor_id
        b = next(p for p in room.players if p.seat == 1).contributor_id
        duo.describe(db, room, db.get(Contributor, a), "Yana misi")
        duo.guess(db, room, db.get(Contributor, b), rnd.option_ids[0])

    item = client.get("/taller/next", headers=auth(reviewer)).json()
    assert item["type"] == "new_sentence" and item["proposed"] == "Yana misi"
    assert item["context"]["image_url"].startswith("/media/duo/")

    client.put(f"/duo/rooms/{code}/consent", headers=auth(ta), json={"consent": False})
    with SessionLocal() as db:
        c = db.scalars(select(Contribution).where(Contribution.type == "new_sentence")).one()
        assert c.status == "withdrawn" and "proposed" not in c.payload
    assert client.get("/taller/next", headers=auth(reviewer)).status_code == 204
    state = client.get(f"/duo/rooms/{code}", headers=auth(ta)).json()
    assert state["round"]["description"] is None


def test_room_rules(client, catalog):
    ta, tb, tc = tokens(client, 3)
    code = client.post("/duo/rooms", headers=auth(ta)).json()["code"]
    with SessionLocal() as db:
        with pytest.raises(duo.DuoError) as e:
            duo.start_round(db, duo.get_room(db, code))
        assert e.value.status == 409  # falta el segundo participante
    client.post(f"/duo/rooms/{code}/join", headers=auth(tb))
    assert client.post(f"/duo/rooms/{code}/join", headers=auth(tb)).json()["seat"] == 1  # reconexión
    assert client.post(f"/duo/rooms/{code}/join", headers=auth(tc)).status_code == 409
    assert client.get(f"/duo/rooms/{code}", headers=auth(tc)).status_code == 403
    assert client.post("/duo/rooms/ZZZZZZ/join", headers=auth(tc)).status_code == 404


def test_websocket_rejects_outsiders(client, catalog):
    from starlette.websockets import WebSocketDisconnect

    ta, tc = tokens(client, 2)
    code = client.post("/duo/rooms", headers=auth(ta)).json()["code"]
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(f"/duo/ws/{code}?token={tc}"):
            pass
    assert e.value.code == 4403
