"""Adaptador simulado: respuestas deterministas con la estructura correcta (§10.3)."""

import hashlib

import numpy as np

from app.adapters.base import ModelAdapter, l2_normalize


class MockAdapter(ModelAdapter):
    name = "mock"
    dim = 32

    def translate(self, texts: list[str], lang: str) -> list[str]:
        return [f"[{lang}] {t}" for t in texts]

    def translate_inverse(self, texts: list[str], lang: str) -> list[str]:
        return [f"[spa] {t}" for t in texts]

    def embed(self, texts: list[str], lang: str) -> np.ndarray:
        rows = []
        for t in texts:
            seed = int.from_bytes(hashlib.sha256(f"{lang}:{t}".encode()).digest()[:8], "little")
            rows.append(np.random.default_rng(seed).standard_normal(self.dim))
        return l2_normalize(np.array(rows).reshape(len(texts), self.dim))

    def embedding_model(self, lang: str) -> str:
        return f"mock-{lang}"
