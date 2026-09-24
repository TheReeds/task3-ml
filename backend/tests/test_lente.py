import subprocess

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Lexeme, VisionLabel
from pipeline.build_lente import norm_es


@pytest.fixture
def labels(corpus):
    with SessionLocal.begin() as db:
        db.add_all([
            VisionLabel(label_set="coco-ssd", label="house", label_es="casa", lang="quy",
                        lexeme_id=corpus["wasi"], method="dictionary"),
            VisionLabel(label_set="coco-ssd", label="cup", label_es="taza", lang="quy"),
            VisionLabel(label_set="coco-ssd", label="bottle", label_es="botella", lang="quy"),
        ])


@pytest.fixture
def people(client):
    def make(n):
        return [{"Authorization": f"Bearer {client.post('/auth/anonymous').json()['token']}"}
                for _ in range(n)]
    return make


def accept_by(client, reviewers, cid):
    for h in reviewers:
        r = client.post("/taller/reviews", json={"contribution_id": cid, "verdict": "accept"}, headers=h)
    return r.json()["status"]


def webm_stream_bytes(seconds: float) -> bytes:
    """WebM escrito como flujo, sin duración en la cabecera (como MediaRecorder de Chrome)."""
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-c:a", "libopus", "-f", "webm", "pipe:1"], capture_output=True, check=True).stdout


def wav_bytes(seconds: float) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-f", "wav", "pipe:1"], capture_output=True, check=True).stdout


def test_norm_es():
    assert norm_es("El Plato (hondo).") == "plato"
    assert norm_es("Avión") == "avion"


def test_labels_and_gaps(client, labels):
    data = client.get("/lente/labels").json()
    assert (data["mapped"], data["total"]) == (1, 3)
    house = next(x for x in data["labels"] if x["label"] == "house")
    assert (house["lemma"], house["gloss"], house["method"]) == ("wasi", "casa", "dictionary")
    gaps = client.get("/lente/labels?gaps_only=true").json()["labels"]
    assert {g["label"] for g in gaps} == {"cup", "bottle"}


def test_new_lemma_fills_gap(client, labels, people):
    author, *revs = people(4)
    r = client.post("/contributions", headers=author, json={
        "type": "new_lemma", "lemma": "Qiru", "gloss": "vaso de madera", "origin_module": "lente",
        "vision_label": "cup"})
    assert r.status_code == 201 and r.json()["payload"]["label_es"] == "taza"
    item = client.get("/taller/next", headers=revs[0]).json()
    assert item["context"]["vision_label"] == "taza"
    assert accept_by(client, revs, r.json()["id"]) == "accepted"
    cup = next(x for x in client.get("/lente/labels").json()["labels"] if x["label"] == "cup")
    assert (cup["lemma"], cup["method"]) == ("qiru", "community")
    with SessionLocal() as db:
        assert db.scalars(select(Lexeme.is_concrete).where(Lexeme.lemma == "qiru")).one()


def test_existing_lemma_can_be_linked_to_gap(client, corpus, labels, people):
    author, *revs = people(4)
    r = client.post("/contributions", headers=author, json={
        "type": "new_lemma", "lemma": "yaku", "origin_module": "lente", "vision_label": "bottle"})
    assert r.status_code == 201
    assert accept_by(client, revs, r.json()["id"]) == "accepted"
    bottle = next(x for x in client.get("/lente/labels").json()["labels"] if x["label"] == "bottle")
    assert (bottle["lemma"], bottle["method"], bottle["lexeme_id"]) == ("yaku", "community", corpus["yaku"])


def test_label_conflicts(client, labels, people):
    h, other, *revs = people(5)
    assert client.post("/contributions", headers=h, json={
        "type": "new_lemma", "lemma": "x", "vision_label": "house"}).status_code == 409
    assert client.post("/contributions", headers=h, json={
        "type": "new_lemma", "lemma": "x", "vision_label": "nope"}).status_code == 422
    # dos propuestas para el mismo vacío: la segunda, aplicada después, queda en conflicto
    a = client.post("/contributions", headers=h, json={
        "type": "new_lemma", "lemma": "yaku", "vision_label": "cup"}).json()["id"]
    b = client.post("/contributions", headers=other, json={
        "type": "new_lemma", "lemma": "wasi", "vision_label": "cup"}).json()["id"]
    assert accept_by(client, revs, a) == "accepted"
    assert accept_by(client, revs, b) == "stale"


def test_audio_recording_cycle(client, corpus, people):
    author, *revs = people(4)
    files = {"file": ("rec.wav", wav_bytes(1.0), "audio/wav")}
    data = {"lexeme_id": str(corpus["yaku"]), "consent": "true"}
    r = client.post("/contributions/audio", headers=author, data=data, files=files)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["type"] == "audio_recording" and 900 <= c["payload"]["duration_ms"] <= 1100
    assert client.get(c["payload"]["proposed"]).status_code == 200  # el revisor puede escucharla
    assert accept_by(client, revs, c["id"]) == "accepted"
    lx = client.get(f"/lexemes/{corpus['yaku']}").json()
    assert lx["audio_origin"] == "community" and lx["audio_url"] == c["payload"]["proposed"]
    assert lx["audio_url_m4a"].endswith(".m4a") and client.get(lx["audio_url_m4a"]).status_code == 200
    assert lx["gloss"] == "agua"  # el resto del lema se conserva


def test_audio_validation(client, corpus, people):
    h = people(1)[0]
    ok = {"lexeme_id": str(corpus["yaku"]), "consent": "true"}

    def post(data, content):
        return client.post("/contributions/audio", headers=h, data=data,
                           files={"file": ("a.wav", content, "audio/wav")})

    assert post(ok, webm_stream_bytes(1.5)).status_code == 201  # MediaRecorder/Chrome
    assert post({**ok, "consent": "false"}, wav_bytes(1)).status_code == 422
    assert post(ok, wav_bytes(0.1)).status_code == 422
    assert post(ok, wav_bytes(8)).status_code == 422
    assert post(ok, b"not audio").status_code == 422
    assert post({**ok, "lexeme_id": "99999"}, wav_bytes(1)).status_code == 404
