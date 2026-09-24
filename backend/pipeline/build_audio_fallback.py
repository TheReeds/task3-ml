"""Copia AAC (.m4a) de cada audio Ogg/Opus, para navegadores sin Opus en Ogg (iOS antiguos).

La API devuelve `audio_url` (Ogg/Opus, más liviano) y `audio_url_m4a` cuando existe la copia;
el cliente elige con `canPlayType`. Solo genera las copias que faltan.

Uso: uv run python -m pipeline.build_audio_fallback
"""

import subprocess
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings


def to_m4a(src) -> bool:
    dest = src.with_suffix(".m4a")
    if dest.exists():
        return False
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-c:a", "aac",
         "-b:a", "48k", "-movflags", "+faststart", str(dest)],
        check=True,
    )
    return True


def main() -> None:
    media = get_settings().media_dir
    sources = sorted(p for p in media.rglob("*.ogg") if "contrib" not in p.parts)
    with ThreadPoolExecutor(max_workers=8) as pool:
        made = sum(pool.map(to_m4a, sources))
    print(f"copias m4a nuevas: {made} (de {len(sources)} audios)")


if __name__ == "__main__":
    main()
