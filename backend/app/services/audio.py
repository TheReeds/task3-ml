"""Recepción de grabaciones aportadas por usuarios (Lente, §7.2)."""

import json
import subprocess
import tempfile
import uuid
from pathlib import Path

from app.config import get_settings

MAX_BYTES = 2 * 1024 * 1024
MIN_MS, MAX_MS = 300, 6000


class AudioError(Exception):
    pass


def probe_duration_ms(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    try:
        return round(float(json.loads(out.stdout)["format"]["duration"]) * 1000)
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        raise AudioError("El archivo no es un audio legible") from e


def store_recording(data: bytes, lang: str) -> tuple[str, int]:
    """Valida y normaliza a Ogg/Opus mono 48 kHz. Devuelve (ruta relativa en media, duración ms)."""
    if len(data) > MAX_BYTES:
        raise AudioError("La grabación supera los 2 MB")
    with tempfile.NamedTemporaryFile(suffix=".upload") as tmp:
        tmp.write(data)
        tmp.flush()
        duration = probe_duration_ms(Path(tmp.name))
        if not MIN_MS <= duration <= MAX_MS:
            raise AudioError(f"La grabación debe durar entre {MIN_MS / 1000:g} y {MAX_MS / 1000:g} s")
        rel = f"{lang}/contrib/{uuid.uuid4().hex}.ogg"
        dest = get_settings().media_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", tmp.name, "-vn", "-ac", "1", "-ar", "48000",
             "-c:a", "libopus", "-b:a", "32k", str(dest)],
            capture_output=True, check=False,
        )
        if result.returncode != 0:
            raise AudioError("No se pudo procesar el audio")
    return rel, duration
