"""Extracción de vocabulario y generación de vectores a nivel de lema (§9.3, pasos 4 y 5).

Entrada:  diccionario y textos de AmericasNLP (quy).
Salida:   data/processed/corpus/<lang>/lexicon.jsonl   lemas con glosa y frecuencia
          data/models/<lang>/fasttext_lemma.model      vectores (consumidos por el adaptador hf)
          data/models/<lang>/lemmas.json               lemas conocidos por el lematizador

Uso: uv run python -m pipeline.build_lexicon
"""

import json
import time
from collections import Counter

from app.nlp.quechua import FUNCTION_WORDS, lemmatize, normalize, tokenize
from pipeline.common import corpus_dir, models_dir, read_lines

LANG = "quy"
TEXT_SOURCES = ["americasnlp/train.quy", "americasnlp/dev.quy"]
MIN_FREQ_FOR_LEXICON = 1


def load_dictionary() -> dict[str, str]:
    """Lemas de una palabra del diccionario, normalizados → glosa (la primera si hay repetidos)."""
    quy = [q.strip().strip(" .").lower() for q in read_lines("americasnlp/dict.quy")]
    es = [e.strip().strip(" .") for e in read_lines("americasnlp/dict.es")]
    lemmas: dict[str, str] = {}
    for q, e in zip(quy, es, strict=True):
        if len(q.split()) == 1 and len(q) >= 3:
            lemmas.setdefault(normalize(q), e)
    return lemmas


def main() -> None:
    from gensim.models import FastText

    lemmas = load_dictionary()
    sentences = [
        [lemmatize(normalize(w), lemmas) or normalize(w) for w in tokenize(line)]
        for src in TEXT_SOURCES
        for line in read_lines(src)
    ]
    freq = Counter(w for s in sentences for w in s)

    rows = [
        {
            "lemma": lemma,
            "gloss": gloss,
            "frequency": freq[lemma],
            "is_function_word": lemma in FUNCTION_WORDS or "sufijo" in gloss.lower(),
        }
        for lemma, gloss in sorted(lemmas.items())
        if freq[lemma] >= MIN_FREQ_FOR_LEXICON
    ]
    out = corpus_dir(LANG) / "lexicon.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"lexicon: {len(rows)} lemas atestiguados → {out}")

    t0 = time.time()
    # bucket reducido: la tabla de n-gramas por defecto (2M) ocupa ~1.6 GB en disco
    ft = FastText(
        sentences, vector_size=200, window=5, min_count=3, sg=1, epochs=10,
        workers=12, min_n=4, max_n=6, bucket=200_000, seed=13,
    )
    mdir = models_dir(LANG)
    ft.save(str(mdir / "fasttext_lemma.model"))
    (mdir / "lemmas.json").write_text(json.dumps(sorted(lemmas), ensure_ascii=False), encoding="utf-8")
    print(f"fasttext: vocab {len(ft.wv):,} en {time.time() - t0:.0f} s → {mdir}")


if __name__ == "__main__":
    main()
