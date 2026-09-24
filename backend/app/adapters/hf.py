"""Adaptador con modelos públicos locales, sustituto del modelo del curso.

- Traducción: NLLB-200 distilled 600M (HuggingFace).
- Vectores: FastText a nivel de lema entrenado por `pipeline.build_lexicon`.

Los modelos se cargan de forma diferida y una sola vez por proceso.
"""

import json
import threading
from functools import cached_property

import numpy as np

from app.adapters.base import ModelAdapter, l2_normalize
from app.config import get_settings
from app.nlp.quechua import lemmatize, normalize, tokenize

NLLB_MODEL = "facebook/nllb-200-distilled-600M"
NLLB_CODES = {"quy": "quy_Latn", "ayr": "ayr_Latn", "spa": "spa_Latn"}
EMBED_VERSION = "fasttext-lemma-v2"


class HFAdapter(ModelAdapter):
    name = "hf"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._vectors: dict[str, tuple] = {}

    # --- traducción -------------------------------------------------------

    @cached_property
    def _nllb(self):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        tok = AutoTokenizer.from_pretrained(NLLB_MODEL)
        model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL, dtype=dtype).to(device).eval()
        return tok, model, device

    def _generate(self, texts: list[str], src: str, tgt: str) -> list[str]:
        import torch

        tok, model, device = self._nllb
        out: list[str] = []
        with self._lock:  # el tokenizador guarda src_lang como estado
            tok.src_lang = NLLB_CODES[src]
            for i in range(0, len(texts), 16):
                batch = tok(texts[i : i + 16], return_tensors="pt", padding=True, truncation=True)
                with torch.no_grad():
                    gen = model.generate(
                        **batch.to(device),
                        forced_bos_token_id=tok.convert_tokens_to_ids(NLLB_CODES[tgt]),
                        max_new_tokens=256,
                        max_length=None,
                    )
                out += tok.batch_decode(gen, skip_special_tokens=True)
        return out

    def translate(self, texts: list[str], lang: str) -> list[str]:
        return self._generate(texts, "spa", lang)

    def translate_inverse(self, texts: list[str], lang: str) -> list[str]:
        return self._generate(texts, lang, "spa")

    # --- vectores ---------------------------------------------------------

    def _load_vectors(self, lang: str):
        if lang not in self._vectors:
            from gensim.models import FastText

            model_dir = get_settings().models_dir / lang
            # mmap: la tabla de n-gramas (~160 MB) se lee del disco bajo demanda, sin copiarla
            # entera a memoria (los planes gratuitos de hosting tienen 512 MB)
            ft = FastText.load(str(model_dir / "fasttext_lemma.model"), mmap="r")
            lemmas = set(json.loads((model_dir / "lemmas.json").read_text(encoding="utf-8")))
            self._vectors[lang] = (ft.wv, lemmas)
        return self._vectors[lang]

    def embed(self, texts: list[str], lang: str) -> np.ndarray:
        wv, lemmas = self._load_vectors(lang)
        rows = []
        for text in texts:
            words = [lemmatize(normalize(w), lemmas) or normalize(w) for w in tokenize(text)]
            rows.append(
                np.mean([wv[w] for w in words], axis=0) if words else np.zeros(wv.vector_size)
            )
        return l2_normalize(np.array(rows).reshape(len(texts), wv.vector_size))

    def embedding_model(self, lang: str) -> str:
        return f"{EMBED_VERSION}-{lang}"
