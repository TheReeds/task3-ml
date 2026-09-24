import os

# Debe fijarse antes de importar la app: el engine se crea al importar app.db
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://corpus:corpus@localhost:5433/corpus_vivo_test"
)
os.environ["MODEL_ADAPTER"] = "mock"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # test_ratelimit prueba el middleware aparte
_MEDIA = __import__("tempfile").mkdtemp(prefix="corpus-vivo-media-")
os.environ["MEDIA_DIR"] = _MEDIA
__import__("atexit").register(__import__("shutil").rmtree, _MEDIA, True)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.models import Alignment, Entry, Lexeme, Translation  # noqa: E402

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")


@pytest.fixture(scope="session", autouse=True)
def schema():
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(ALEMBIC_INI), "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE reviews, gold_items, contributions, contributors, embeddings, "
            "alignments, translations, radar_puzzles, vision_labels, duo_rounds, duo_players, "
            "link_codes, contributor_tokens, events, topics, "
            "duo_rooms, duo_images, entries, lexemes "
            "RESTART IDENTITY CASCADE"
        ))


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def corpus():
    """Mini corpus: 3 entradas con dificultad creciente y 2 lemas."""
    with SessionLocal.begin() as db:
        wasi = Lexeme(lang="quy", lemma="wasi", gloss="casa", frequency=50, source="test")
        yaku = Lexeme(lang="quy", lemma="yaku", gloss="agua", frequency=30, source="test")
        db.add_all([wasi, yaku])
        db.flush()
        entries = []
        for i, (txt, diff) in enumerate([("wasipi kani", 0.1), ("yakuta upyani", 0.5), ("hatun wasi", 0.9)]):
            e = Entry(lang="quy", text=txt, difficulty=diff, source="test", audio_path=f"quy/{i}.ogg",
                      audio_origin="synthetic", duration_ms=1000, speaker="tts")
            db.add(e)
            db.flush()
            db.add(Translation(entry_id=e.id, lang="spa", text=f"trad {i}", origin="dataset"))
            for pos, tok in enumerate(txt.split()):
                lex = wasi if tok.startswith("wasi") else yaku if tok.startswith("yaku") else None
                db.add(Alignment(entry_id=e.id, position=pos, token=tok, start_ms=pos * 400,
                                 end_ms=pos * 400 + 350, lexeme_id=lex.id if lex else None))
            entries.append(e.id)
        return {"entries": entries, "wasi": wasi.id, "yaku": yaku.id}


@pytest.fixture
def auth(client):
    token = client.post("/auth/anonymous").json()["token"]
    return {"Authorization": f"Bearer {token}"}
