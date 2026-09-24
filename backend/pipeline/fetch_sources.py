"""Descarga las fuentes públicas usadas como corpus provisional (quechua).

Mientras el corpus del curso no esté disponible, se usan:
  - AmericasNLP 2021, par quechua (quy) – español: dev (curado) y train (volumen).
  - Vectores fastText de Wikipedia en quechua (wiki.qu), como línea base de embeddings.

Uso: uv run python -m pipeline.fetch_sources
"""

import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

AMERICASNLP = (
    "https://raw.githubusercontent.com/AmericasNLP/americasnlp2021/main/data/quechua-spanish"
)

SOURCES = {
    "americasnlp/dev.quy": f"{AMERICASNLP}/dev.quy",
    "americasnlp/dev.es": f"{AMERICASNLP}/dev.es",
    "americasnlp/train.quy": f"{AMERICASNLP}/train.quy",
    "americasnlp/train.es": f"{AMERICASNLP}/train.es",
    "americasnlp/dict.quy": f"{AMERICASNLP}/dict.quy",
    "americasnlp/dict.es": f"{AMERICASNLP}/dict.es",
    "fasttext/wiki.qu.vec": "https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.qu.vec",
}


def main() -> None:
    for rel, url in SOURCES.items():
        dest = RAW / rel
        if dest.exists():
            print(f"[skip] {rel}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"[get ] {rel}")
        urllib.request.urlretrieve(url, dest)


if __name__ == "__main__":
    main()
