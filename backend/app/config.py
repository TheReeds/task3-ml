from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://corpus:corpus@localhost:5433/corpus_vivo"
    model_adapter: str = "mock"  # mock | hf | remote
    default_lang: str = "quy"
    media_dir: Path = BASE_DIR / "data" / "media"
    media_url: str = "/media"
    models_dir: Path = BASE_DIR / "data" / "models"
    cors_origins: list[str] = ["http://localhost:5173"]
    timezone: str = "America/Lima"

    # Taller: consenso ponderado (§7.3) y confiabilidad (§7.4)
    consensus_min_reviews: int = 2  # ninguna aprobación unilateral
    consensus_min_weight: float = 1.5  # con pesos 0.5 hacen falta 3 revisores; con pesos altos, 2
    consensus_accept: float = 0.7
    consensus_reject: float = 0.3
    consensus_max_reviews: int = 7  # sin consenso tras N juicios firmes → se rechaza
    gold_every: int = 5  # se intercala un elemento de control cada N revisiones (empezando por la 1.ª)
    reliability_cap: float = 0.8  # techo para revisores no nativos o sin desempeño probado
    native_min_gold: int = 5
    native_min_accuracy: float = 0.8

    # Radar (§6.4)
    radar_min_frequency: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
