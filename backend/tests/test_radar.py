from datetime import date

import numpy as np
import pytest
from sqlalchemy import select

from app.adapters import get_adapter
from app.db import SessionLocal
from app.models import Embedding, Lexeme, RadarPuzzle
from app.services import radar


@pytest.fixture
def vocab():
    """Vocabulario con vectores controlados: 'yaku' cerca de 'qucha', lejos de 'rumi'."""
    base = {
        "yaku": [1, 0, 0], "qucha": [0.9, 0.1, 0], "pukyu": [0.8, 0.3, 0], "rumi": [0, 0, 1],
        "maskay": [0, 1, 0], "maskaspa": [0, 1, 0.01], "chay": [0.5, 0.5, 0], "animal": [0.2, 0.2, 0.9],
    }
    gloss = {"yaku": "agua", "qucha": "lago", "pukyu": "manantial", "rumi": "piedra",
             "maskay": "buscar", "maskaspa": "buscando", "chay": "eso", "animal": "animal"}
    model = get_adapter().embedding_model("quy")
    with SessionLocal.begin() as db:
        for lemma, vec in base.items():
            lx = Lexeme(lang="quy", lemma=lemma, gloss=gloss[lemma], frequency=100, source="test",
                        is_function_word=lemma == "chay")
            db.add(lx)
            db.flush()
            db.add(Embedding(owner_type="lexeme", owner_id=lx.id, model=model,
                             vector=np.array(vec + [0] * 29, dtype=np.float32)))
    return base


def test_eligible_excludes_function_words_loans_and_derived(vocab):
    with SessionLocal() as db:
        lex, mat, _ = radar._vocabulary(db, "quy")
        roots, _ = radar.roots_only(lex, mat)
        assert "maskaspa" not in {lx.lemma for lx in roots}
        eligible = {lx.lemma for lx in radar.eligible_targets(roots, 50)}
    assert eligible == {"yaku", "qucha", "pukyu", "rumi", "maskay"}


def test_pick_target_cycles_without_repeating(vocab):
    with SessionLocal() as db:
        lex, _, _ = radar._vocabulary(db, "quy")
    cands = radar.eligible_targets(lex, 50)
    days = [radar.pick_target(cands, "quy", date.fromordinal(date(2026, 1, 1).toordinal() + i)).lemma
            for i in range(len(cands))]
    assert sorted(days) == sorted(lx.lemma for lx in cands)


def make_puzzle(lemma: str) -> int:
    with SessionLocal.begin() as db:
        lex, mat, model = radar._vocabulary(db, "quy")
        lex, mat = radar.roots_only(lex, mat)
        idx = next(i for i, lx in enumerate(lex) if lx.lemma == lemma)
        p = RadarPuzzle(lang="quy", day=radar.today(), lexeme_id=lex[idx].id, model=model,
                        ranking=radar.build_ranking(lex, mat, idx))
        db.add(p)
        db.flush()
        return p.id


def test_ranking_and_guesses(client, vocab):
    make_puzzle("yaku")
    today = client.get("/radar/today").json()
    assert today["letters"] == 4 and today["vocabulary_size"] == 7

    g = client.post("/radar/guess", json={"word": "Qucha"}).json()
    assert (g["lemma"], g["rank"], g["percentile"], g["gloss"]) == ("qucha", 2, pytest.approx(83.3), "lago")
    far = client.post("/radar/guess", json={"word": "rumi"}).json()
    assert far["percentile"] < g["percentile"]
    # forma flexionada del objetivo = acierto
    assert client.post("/radar/guess", json={"word": "yakukunapi"}).json()["solved"] is True


def test_conjugated_guess_maps_to_root(client, vocab):
    make_puzzle("maskay")
    assert client.post("/radar/guess", json={"word": "maskaspa"}).json()["solved"] is True


def test_unknown_word_offers_contribution(client, vocab):
    make_puzzle("yaku")
    g = client.post("/radar/guess", json={"word": "sara"}).json()
    assert g["known"] is False and g["can_contribute"] is True
    assert g["suggestion"] == {"type": "new_lemma", "lang": "quy", "lemma": "sara", "origin_module": "radar"}
    token = client.post("/auth/anonymous").json()["token"]
    r = client.post("/contributions", json=g["suggestion"], headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201


def test_multiword_guess_rejected(client, vocab):
    make_puzzle("yaku")
    assert client.post("/radar/guess", json={"word": "yaku qucha"}).status_code == 422


def test_answer_hidden_until_give_up(client, vocab):
    pid = make_puzzle("yaku")
    assert client.get(f"/radar/puzzles/{pid}/answer").status_code == 403
    ans = client.get(f"/radar/puzzles/{pid}/answer?give_up=true").json()
    assert ans["lemma"] == "yaku" and ans["neighbors"][0]["lemma"] == "qucha"


def test_today_creates_puzzle_once(client, vocab):
    a = client.get("/radar/today").json()["puzzle_id"]
    b = client.get("/radar/today").json()["puzzle_id"]
    assert a == b
    with SessionLocal() as db:
        assert len(db.scalars(select(RadarPuzzle)).all()) == 1


def test_today_without_vocabulary_is_503(client):
    assert client.get("/radar/today").status_code == 503


def test_archive_creates_recent_days(client, vocab):
    items = client.get("/radar/puzzles?days=3").json()
    assert [i["is_today"] for i in items] == [True, False, False]
    days = [i["day"] for i in items]
    assert days == sorted(days, reverse=True) and len(set(days)) == 3
    past = items[1]["puzzle_id"]
    # un día pasado se puede jugar y revelar sin rendirse
    assert client.post("/radar/guess", json={"word": "yaku", "puzzle_id": past}).status_code == 200
    assert client.get(f"/radar/puzzles/{past}/answer").status_code == 200
    # idempotente: no duplica puzzles
    assert [i["puzzle_id"] for i in client.get("/radar/puzzles?days=3").json()] == [i["puzzle_id"] for i in items]
