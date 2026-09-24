from functools import lru_cache

from app.adapters.base import ModelAdapter
from app.config import get_settings


@lru_cache
def get_adapter() -> ModelAdapter:
    kind = get_settings().model_adapter
    if kind == "mock":
        from app.adapters.mock import MockAdapter

        return MockAdapter()
    if kind == "hf":
        from app.adapters.hf import HFAdapter

        return HFAdapter()
    raise ValueError(f"MODEL_ADAPTER desconocido: {kind!r} (opciones: mock, hf)")
