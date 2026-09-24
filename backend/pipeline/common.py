from pathlib import Path

from app.config import get_settings

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def read_lines(rel: str) -> list[str]:
    return (RAW / rel).read_text(encoding="utf-8-sig").splitlines()


def corpus_dir(lang: str) -> Path:
    path = PROCESSED / "corpus" / lang
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir(lang: str) -> Path:
    path = get_settings().models_dir / lang
    path.mkdir(parents=True, exist_ok=True)
    return path


def media_dir(lang: str) -> Path:
    path = get_settings().media_dir / lang
    path.mkdir(parents=True, exist_ok=True)
    return path
