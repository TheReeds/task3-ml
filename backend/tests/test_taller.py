import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Contribution, Contributor, Embedding, GoldItem, Lexeme


@pytest.fixture
def people(client):
    def make(n):
        out = []
        for _ in range(n):
            tok = client.post("/auth/anonymous").json()["token"]
            out.append({"Authorization": f"Bearer {tok}"})
        return out
    return make


def propose(client, headers, body):
    r = client.post("/contributions", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def review(client, headers, cid, verdict):
    return client.post("/taller/reviews", json={"contribution_id": cid, "verdict": verdict}, headers=headers)


def test_transcription_fix_full_cycle(client, corpus, people):
    author, *reviewers = people(4)
    entry = corpus["entries"][0]
    cid = propose(client, author, {"type": "transcription_fix", "entry_id": entry, "position": 1, "token": "kachkani"})

    item = client.get("/taller/next", headers=reviewers[0]).json()
    assert item["contribution_id"] == cid
    assert item["context"]["text"] == "wasipi kani"
    assert (item["original"], item["proposed"]) == ("kani", "kachkani")
    assert item["proposer_reliability"] == 0.5

    assert review(client, reviewers[0], cid, "accept").json()["status"] == "pending"
    assert review(client, reviewers[1], cid, "unsure").json()["status"] == "pending"
    assert review(client, reviewers[2], cid, "accept").json()["status"] == "pending"  # peso 1.0
    extra = people(1)[0]
    assert review(client, extra, cid, "accept").json()["status"] == "accepted"

    # nueva versión vigente, original intacto y trazable
    current = client.get("/radio/stations/facil/next").json()
    assert current["text"] == "wasipi kachkani"
    assert current["supersedes_id"] == entry
    assert current["translation"]["text"] == "trad 0"
    assert client.get(f"/entries/{entry}").json()["text"] == "wasipi kani"
    assert [h["id"] for h in client.get(f"/entries/{entry}/history").json()] == [current["id"], entry]
    with SessionLocal() as db:
        assert db.scalar(select(Embedding).where(Embedding.owner_type == "entry",
                                                 Embedding.owner_id == current["id"])) is not None


def test_review_rules(client, corpus, people):
    author, reviewer = people(2)
    cid = propose(client, author, {"type": "new_lemma", "lemma": "sara", "gloss": "maíz"})
    assert client.get("/taller/next", headers=author).status_code == 204  # no se ofrece la propia
    assert review(client, author, cid, "accept").status_code == 403
    assert review(client, reviewer, cid, "accept").status_code == 201
    assert review(client, reviewer, cid, "accept").status_code == 409
    assert client.get("/taller/next", headers=reviewer).status_code == 204
    assert review(client, reviewer, 9999, "accept").status_code == 404


def test_new_lemma_and_gloss_fix_applied(client, corpus, people):
    author, *revs = people(4)
    c1 = propose(client, author, {"type": "new_lemma", "lemma": "sara", "gloss": "maíz"})
    c2 = propose(client, author, {"type": "gloss_fix", "lexeme_id": corpus["wasi"], "gloss": "casa, hogar"})
    for r in revs:
        review(client, r, c1, "accept")
        review(client, r, c2, "accept")
    with SessionLocal() as db:
        sara = db.scalars(select(Lexeme).where(Lexeme.lemma == "sara")).one()
        assert sara.source == "community" and sara.contribution_id == c1
    # el token sigue apuntando al id antiguo, pero el panel muestra la versión vigente
    lx = client.get(f"/lexemes/{corpus['wasi']}").json()
    assert lx["gloss"] == "casa, hogar" and lx["id"] != corpus["wasi"]
    assert len(lx["examples"]) == 2


def test_translation_fix_and_stale_conflict(client, corpus, people):
    a, b, *revs = people(5)
    tr_id = client.get(f"/entries/{corpus['entries'][1]}").json()["translation"]["id"]
    c1 = propose(client, a, {"type": "translation_fix", "translation_id": tr_id, "text": "Bebo agua."})
    c2 = propose(client, b, {"type": "translation_fix", "translation_id": tr_id, "text": "Tomo agua."})
    for r in revs:
        review(client, r, c1, "accept")
    tr = client.get(f"/entries/{corpus['entries'][1]}").json()["translation"]
    assert (tr["text"], tr["origin"]) == ("Bebo agua.", "community")
    # c2 se propuso sobre la versión anterior: al aceptarse no pisa el cambio
    statuses = [review(client, r, c2, "accept").json()["status"] for r in revs]
    assert statuses[-1] == "stale"


def test_rejection_leaves_corpus_untouched(client, corpus, people):
    author, *revs = people(4)
    cid = propose(client, author, {"type": "gloss_fix", "lexeme_id": corpus["yaku"], "gloss": "fuego"})
    for r in revs:
        review(client, r, cid, "reject")
    assert client.get(f"/lexemes/{corpus['yaku']}").json()["gloss"] == "agua"


def test_gold_items_calibrate_reliability(client, corpus, people):
    with SessionLocal.begin() as db:
        for expected in ("reject", "accept"):
            c = Contribution(lang="quy", type="gloss_fix", target_type="lexeme", target_id=corpus["yaku"],
                             payload={"lemma": "yaku", "original": "agua", "proposed": "fuego"}
                             if expected == "reject" else
                             {"lemma": "yaku", "original": "fuego", "proposed": "agua"}, status="gold")
            db.add(c)
            db.flush()
            db.add(GoldItem(contribution_id=c.id, expected_verdict=expected))
    reviewer = people(1)[0]
    item = client.get("/taller/next", headers=reviewer).json()  # la primera revisión es de control
    wrong = "accept" if item["proposed"] == "fuego" else "reject"
    r = review(client, reviewer, item["contribution_id"], wrong)
    assert r.json()["status"] == "pending"  # no revela que era un control
    me = client.get("/auth/me", headers=reviewer).json()
    assert me["reliability"] == pytest.approx(1 / 3, abs=1e-3)
    with SessionLocal() as db:
        assert db.scalars(select(Contributor.gold_seen)).all() == [1]


def test_native_flag_only_helps_with_proven_accuracy(client, people):
    h = people(1)[0]
    me = client.patch("/auth/me", json={"is_native_speaker": True}, headers=h).json()
    assert me["is_native_speaker"] and me["reliability"] == 0.5


def test_impact_and_export(client, corpus, people):
    author, *revs = people(4)
    cid = propose(client, author, {"type": "new_lemma", "lemma": "sara", "gloss": "maíz"})
    propose(client, author, {"type": "new_lemma", "lemma": "inti", "gloss": "sol"})
    for r in revs:
        review(client, r, cid, "accept")
    imp = client.get("/taller/impact").json()
    assert imp["contributions"]["accepted"] == 1 and imp["contributions"]["pending"] == 1
    assert imp["accepted_by_type"] == {"new_lemma": 1}
    assert imp["reviewers"] == 3 and imp["fleiss_kappa"] is None  # acuerdo unánime de una sola categoría
    lines = client.get("/taller/export").text.strip().splitlines()
    assert len(lines) == 1 and '"proposed": "sara"' in lines[0] and '"contributor": "anon-' in lines[0]
    csv_text = client.get("/taller/export?format=csv").text
    assert csv_text.splitlines()[0].startswith("id,lang,type")


def test_queue_type_filter_and_timeline(client, corpus, people):
    author, reviewer = people(2)
    propose(client, author, {"type": "new_lemma", "lemma": "sara", "gloss": "maíz"})
    cid = propose(client, author, {"type": "gloss_fix", "lexeme_id": corpus["yaku"], "gloss": "agua dulce"})
    item = client.get("/taller/next", params={"type": "gloss_fix"}, headers=reviewer).json()
    assert item["contribution_id"] == cid
    both = client.get("/taller/next", params=[("type", "gloss_fix"), ("type", "new_lemma")], headers=reviewer)
    assert both.status_code == 200
    assert client.get("/taller/next", params={"type": "audio_recording"}, headers=reviewer).status_code == 204
    assert client.get("/taller/next", params={"type": "nope"}, headers=reviewer).status_code == 422
    review(client, reviewer, cid, "accept")
    timeline = client.get("/taller/impact?days=7").json()["timeline"]
    assert len(timeline) == 7
    assert timeline[-1]["created"] == 2 and timeline[-1]["reviews"] == 1
