"""Ingesta del corpus procesado a la base de datos (§9.3, pasos 2, 5 y 7).

Lee lexicon.jsonl y entries.jsonl, vincula cada token con su lema, calcula el índice de
dificultad y genera los vectores a través del adaptador del modelo (contrato §10.2).

La ingesta reemplaza el núcleo del corpus de la lengua indicada y regenera sus ids, por lo que
se niega a ejecutarse si ya hay contribuciones sobre esa lengua (quedarían apuntando a registros
inexistentes). Solo debe ejecutarse antes de la puesta en servicio o al cambiar de corpus.

Uso: uv run python -m pipeline.ingest [--lang quy] [--force]
"""

import argparse
import json
import math

import numpy as np
from sqlalchemy import delete, func, insert, select

from app.adapters import get_adapter
from app.db import SessionLocal
from app.models import (
    Alignment,
    Contribution,
    Embedding,
    Entry,
    GoldItem,
    Lexeme,
    Review,
    Translation,
)
from app.nlp.quechua import lemmatize, normalize, tokenize
from pipeline.common import corpus_dir


def read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def percentile_ranks(values: list[float]) -> list[float]:
    order = np.argsort(np.argsort(values))
    return (order / max(len(values) - 1, 1)).tolist()


def difficulty_scores(rows: list[dict], freq: dict[str, int], lemmas: dict) -> list[float]:
    """Índice de dificultad en [0, 1] (percentil): mitad longitud, mitad rareza léxica media.

    La rareza de un token es -log de la frecuencia relativa de su lema; los tokens sin lema
    conocido cuentan como hápax.
    """
    total = sum(freq.values()) or 1
    lengths, rarities = [], []
    for r in rows:
        words = [normalize(w) for w in tokenize(r["text"])]
        rar = [-math.log((freq.get(lemmatize(w, lemmas) or "", 0) + 1) / total) for w in words]
        lengths.append(len(words))
        rarities.append(sum(rar) / max(len(rar), 1))
    combined = [
        0.5 * a + 0.5 * b
        for a, b in zip(percentile_ranks(lengths), percentile_ranks(rarities), strict=True)
    ]
    # re-escalar a percentil para que los tercios (emisoras fácil/intermedia/difícil) queden parejos
    return [round(x, 4) for x in percentile_ranks(combined)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="quy")
    parser.add_argument("--force", action="store_true", help="re-ingerir aunque haya contribuciones")
    args = parser.parse_args()
    lang = args.lang

    cdir = corpus_dir(lang)
    lexicon = read_jsonl(cdir / "lexicon.jsonl")
    rows = read_jsonl(cdir / "entries.jsonl")
    adapter = get_adapter()
    model_id = adapter.embedding_model(lang)

    with SessionLocal.begin() as db:
        n_contrib = db.scalar(
            select(func.count()).where(Contribution.lang == lang, Contribution.status != "gold")
        )
        if n_contrib and not args.force:
            raise SystemExit(
                f"Hay {n_contrib} contribuciones sobre '{lang}'. Re-ingerir cambiaría los ids a los "
                "que apuntan. Use --force solo en entornos de desarrollo."
            )
        # Los elementos de control apuntan a ids del corpus: se descartan y se vuelven a sembrar
        gold = select(Contribution.id).where(Contribution.lang == lang, Contribution.status == "gold")
        db.execute(delete(Review).where(Review.contribution_id.in_(gold)))
        db.execute(delete(GoldItem).where(GoldItem.contribution_id.in_(gold)))
        db.execute(delete(Contribution).where(Contribution.id.in_(gold)))

        entry_ids = select(Entry.id).where(Entry.lang == lang)
        lexeme_ids = select(Lexeme.id).where(Lexeme.lang == lang)
        db.execute(delete(Embedding).where(Embedding.owner_type == "entry", Embedding.owner_id.in_(entry_ids)))
        db.execute(delete(Embedding).where(Embedding.owner_type == "lexeme", Embedding.owner_id.in_(lexeme_ids)))
        db.execute(delete(Translation).where(Translation.entry_id.in_(entry_ids)))
        db.execute(delete(Alignment).where(Alignment.entry_id.in_(entry_ids)))
        db.execute(delete(Entry).where(Entry.lang == lang))
        db.execute(delete(Lexeme).where(Lexeme.lang == lang))

        # Léxico
        lex_ids = db.scalars(
            insert(Lexeme).returning(Lexeme.id),
            [
                {
                    "lang": lang,
                    "lemma": x["lemma"],
                    "gloss": x["gloss"],
                    "frequency": x["frequency"],
                    "is_function_word": x["is_function_word"],
                    "source": "americasnlp-2021-dict",
                }
                for x in lexicon
            ],
        ).all()
        lemma_to_id = {x["lemma"]: i for x, i in zip(lexicon, lex_ids, strict=True)}
        freq = {x["lemma"]: x["frequency"] for x in lexicon}

        # Entradas, traducciones y alineaciones
        difficulty = difficulty_scores(rows, freq, lemma_to_id)
        e_ids = db.scalars(
            insert(Entry).returning(Entry.id),
            [
                {
                    "lang": lang,
                    "text": r["text"],
                    "audio_path": r.get("audio_path"),
                    "audio_origin": r.get("audio_origin"),
                    "duration_ms": r.get("duration_ms"),
                    "domain": r.get("domain"),
                    "speaker": r.get("speaker"),
                    "difficulty": d,
                    "source": r["source"],
                    "source_ref": r.get("source_ref"),
                }
                for r, d in zip(rows, difficulty, strict=True)
            ],
        ).all()
        db.execute(
            insert(Translation),
            [
                {"entry_id": eid, "lang": "spa", "text": r["translation"], "origin": "dataset"}
                for r, eid in zip(rows, e_ids, strict=True)
                if r.get("translation")
            ],
        )
        alignments = []
        for r, eid in zip(rows, e_ids, strict=True):
            for pos, t in enumerate(r["tokens"]):
                words = tokenize(t["token"])
                lemma = lemmatize(normalize(words[0]), lemma_to_id) if len(words) == 1 else None
                alignments.append({
                    "entry_id": eid,
                    "position": pos,
                    "token": t["token"],
                    "start_ms": t["start_ms"],
                    "end_ms": t["end_ms"],
                    "aligned": t["aligned"],
                    "lexeme_id": lemma_to_id.get(lemma) if lemma else None,
                })
        db.execute(insert(Alignment), alignments)

        # Vectores vía adaptador
        lex_vecs = adapter.embed([x["lemma"] for x in lexicon], lang)
        ent_vecs = adapter.embed([r["text"] for r in rows], lang)
        db.execute(
            insert(Embedding),
            [{"owner_type": "lexeme", "owner_id": i, "model": model_id, "vector": v}
             for i, v in zip(lex_ids, lex_vecs, strict=True)]
            + [{"owner_type": "entry", "owner_id": i, "model": model_id, "vector": v}
               for i, v in zip(e_ids, ent_vecs, strict=True)],
        )

    linked = sum(a["lexeme_id"] is not None for a in alignments)
    print(
        f"[{lang}] lexemes={len(lex_ids)} entries={len(e_ids)} alignments={len(alignments)} "
        f"(con lema: {linked / len(alignments):.0%}) embeddings={model_id} dim={lex_vecs.shape[1]}"
    )
    print("Recuerde volver a sembrar los controles: uv run python -m pipeline.seed_gold")


if __name__ == "__main__":
    main()
