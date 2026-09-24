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


@lru_cache
def get_settings() -> Settings:
    return Settings()
