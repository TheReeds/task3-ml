from app.db import SessionLocal
from app.models import Entry


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_stations_split_by_difficulty(client, corpus):
    stations = {s["id"]: s["entries"] for s in client.get("/radio/stations").json()}
    assert stations["aleatoria"] == 3
    assert (stations["facil"], stations["intermedia"], stations["dificil"]) == (1, 1, 1)
    assert "hablante:tts" not in stations  # una sola voz: sin emisora por hablante


def test_next_returns_full_entry_payload(client, corpus):
    e = client.get("/radio/stations/facil/next").json()
    assert e["text"] == "wasipi kani"
    assert e["audio_url"] == "/media/quy/0.ogg"
    assert e["translation"]["origin"] == "dataset"
    assert [t["token"] for t in e["tokens"]] == ["wasipi", "kani"]
    assert e["tokens"][0]["lexeme_id"] == corpus["wasi"]


def test_ordered_station_chains_and_wraps(client, corpus):
    first, second, third = corpus["entries"]
    nxt = lambda after: client.get(f"/radio/stations/aleatoria/next?after={after}").json()["id"]  # noqa: E731
    assert nxt(first) != first  # aleatoria nunca repite la que acaba de sonar
    # emisora ordenada con una sola entrada: vuelve al principio
    assert client.get(f"/radio/stations/dificil/next?after={third}").json()["id"] == third


def test_unknown_station_404(client, corpus):
    assert client.get("/radio/stations/nope/next").status_code == 404


def test_superseded_entry_is_hidden_and_history_is_kept(client, corpus):
    original = corpus["entries"][0]
    with SessionLocal.begin() as db:
        newer = Entry(lang="quy", text="wasipi kachkani", difficulty=0.1, source="community",
                      supersedes_id=original)
        db.add(newer)
        db.flush()
        newer_id = newer.id
    assert client.get("/radio/stations/facil/next").json()["id"] == newer_id
    history = client.get(f"/entries/{original}/history").json()
    assert [h["id"] for h in history] == [newer_id, original]


def test_lexeme_detail_with_examples(client, corpus):
    lx = client.get(f"/lexemes/{corpus['wasi']}").json()
    assert lx["gloss"] == "casa"
    assert {ex["text"] for ex in lx["examples"]} == {"wasipi kani", "hatun wasi"}


def test_contribution_requires_token(client, corpus):
    r = client.post("/contributions", json={"type": "new_lemma", "lemma": "sara"})
    assert r.status_code == 401


def test_transcription_fix_records_original(client, corpus, auth):
    body = {"type": "transcription_fix", "entry_id": corpus["entries"][0], "position": 1, "token": "kachkani"}
    r = client.post("/contributions", json=body, headers=auth)
    assert r.status_code == 201
    c = r.json()
    assert c["status"] == "pending"
    assert c["payload"] == {"position": 1, "original": "kani", "proposed": "kachkani"}
    # el dato original sigue intacto
    assert client.get(f"/entries/{corpus['entries'][0]}").json()["tokens"][1]["token"] == "kani"


def test_duplicate_pending_contribution_is_idempotent(client, corpus, auth):
    body = {"type": "gloss_fix", "lexeme_id": corpus["yaku"], "gloss": "agua, líquido"}
    a = client.post("/contributions", json=body, headers=auth).json()
    b = client.post("/contributions", json=body, headers=auth).json()
    assert a["id"] == b["id"]


def test_contribution_validation(client, corpus, auth):
    entry = corpus["entries"][0]
    cases = [
        ({"type": "transcription_fix", "entry_id": entry, "position": 9, "token": "x"}, 422),
        ({"type": "transcription_fix", "entry_id": entry, "position": 0, "token": "wasipi"}, 422),
        ({"type": "transcription_fix", "entry_id": 99999, "position": 0, "token": "x"}, 404),
        ({"type": "new_lemma", "lemma": "Wasi"}, 409),
        ({"type": "unknown"}, 422),
    ]
    for body, code in cases:
        assert client.post("/contributions", json=body, headers=auth).status_code == code, body


def test_new_lemma_and_listing(client, corpus, auth):
    r = client.post("/contributions", json={"type": "new_lemma", "lemma": "Sara", "gloss": "maíz"}, headers=auth)
    assert r.json()["payload"]["lemma"] == "sara"
    mine = client.get("/contributions/mine", headers=auth).json()
    assert [c["type"] for c in mine] == ["new_lemma"]


def test_link_code_moves_identity_to_another_device(client):
    first = client.post("/auth/anonymous").json()
    h1 = {"Authorization": f"Bearer {first['token']}"}
    code = client.post("/auth/link-code", headers=h1).json()["code"]
    assert len(code) == 8
    second = client.post("/auth/link", json={"code": code.lower()}).json()
    assert second["contributor_id"] == first["contributor_id"] and second["token"] != first["token"]
    # ambos dispositivos siguen funcionando con la misma identidad
    for t in (first["token"], second["token"]):
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {t}"}).json()
        assert me["id"] == first["contributor_id"]
    # un solo uso
    assert client.post("/auth/link", json={"code": code}).status_code == 400
    assert client.post("/auth/link", json={"code": "ZZZZZZZZ"}).status_code == 400
    assert client.post("/auth/link-code").status_code == 401


def test_expired_link_code_rejected(client):
    from datetime import UTC, datetime, timedelta

    from app.models import LinkCode

    t = client.post("/auth/anonymous").json()["token"]
    code = client.post("/auth/link-code", headers={"Authorization": f"Bearer {t}"}).json()["code"]
    with SessionLocal.begin() as db:
        for lc in db.query(LinkCode).all():
            lc.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.post("/auth/link", json={"code": code}).status_code == 400


def test_search_lexemes(client, corpus):
    def lemmas(q, **params):
        return [x["lemma"] for x in client.get("/lexemes", params={"q": q, **params}).json()]

    assert lemmas("wasi")[0] == "wasi"
    assert lemmas("wasikunapi") == ["wasi"]  # forma flexionada → raíz
    assert lemmas("WASI")[0] == "wasi"
    assert lemmas("agua") == ["yaku"]  # glosa en español
    assert lemmas("zzz") == []
    assert client.get("/lexemes", params={"q": ""}).status_code == 422
    assert lemmas("wasi", concrete="true") == []  # ningún lema del fixture está marcado concreto
    x = client.get("/lexemes", params={"q": "casa"}).json()[0]
    assert x["lemma"] == "wasi" and "audio_url" in x


def test_fold_keeps_enye():
    from app.services.search import fold

    assert fold("Árbol Ñandú") == "arbol ñandu"


def test_languages(client, corpus):
    langs = client.get("/languages").json()
    assert [x["code"] for x in langs] == ["quy"]
    q = langs[0]
    assert q["default"] and q["endonym"] == "Runasimi"
    assert q["counts"]["entries"] == 3 and q["modules"]["radio"] and not q["modules"]["duo"]


def test_topic_stations(client, corpus):
    from app.models import Entry, Topic

    with SessionLocal.begin() as db:
        db.add(Topic(lang="quy", slug="hogar", name="Casa y familia", keywords=["casa", "familia"],
                     method="clustering"))
        for e in db.query(Entry).filter(Entry.id.in_(corpus["entries"][:2])):
            e.domain = "hogar"
    st = {s["id"]: s for s in client.get("/radio/stations").json()}
    assert st["dominio:hogar"]["name"] == "Casa y familia"
    assert st["dominio:hogar"]["entries"] == 2 and "casa" in st["dominio:hogar"]["description"]
    ids = {client.get("/radio/stations/dominio:hogar/next").json()["id"] for _ in range(3)}
    assert ids <= set(corpus["entries"][:2])
    assert client.get("/radio/stations/dominio:nada/next").status_code == 404
