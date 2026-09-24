"""Contrato de interfaz con el modelo externo (doc. técnico §10.2).

La aplicación nunca invoca un modelo directamente: todo pasa por un `ModelAdapter`.
Cuando los equipos del modelo entreguen su servicio, basta con una nueva implementación
(`remote`) y cambiar `MODEL_ADAPTER`; ningún otro componente se modifica (§10.3).

Convención de lenguas: códigos ISO 639-3 (`quy`, `ayr`); el español es implícito.
"""

from abc import ABC, abstractmethod

import numpy as np


class ModelAdapter(ABC):
    #: Identificador de la implementación, se guarda junto a lo que produce
    name: str

    @abstractmethod
    def translate(self, texts: list[str], lang: str) -> list[str]:
        """Español → lengua objetivo."""

    @abstractmethod
    def translate_inverse(self, texts: list[str], lang: str) -> list[str]:
        """Lengua objetivo → español."""

    @abstractmethod
    def embed(self, texts: list[str], lang: str) -> np.ndarray:
        """Palabras u oraciones en la lengua objetivo → matriz (n, dim), filas de norma 1."""

    @abstractmethod
    def embedding_model(self, lang: str) -> str:
        """Identificador estable del espacio vectorial (se guarda en `embeddings.model`)."""

    def score(self, texts: list[str], lang: str) -> list[float | None]:
        """Verosimilitud de cada texto en la lengua objetivo. Operación opcional del contrato."""
        return [None] * len(texts)


def l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return (mat / np.where(norms == 0, 1, norms)).astype(np.float32)
