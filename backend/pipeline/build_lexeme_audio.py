"""Pronunciación de cada lema vigente (Lente, panel de palabra de Radio y Radar).

Mientras no haya grabaciones reales se sintetiza con MMS-TTS (`audio_origin = synthetic`).
Solo se generan los lemas que aún no tienen audio, de modo que las grabaciones aportadas por
la comunidad (versiones nuevas del lema) nunca se sobrescriben.

Debe ejecutarse después de `pipeline.ingest`.
Uso: uv run python -m pipeline.build_lexeme_audio [--lang quy] [--only-concrete]
"""

import argparse
import re

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Lexeme
from app.services.corpus import is_current
from pipeline.build_corpus import encode_opus
from pipeline.common import media_dir

TTS_MODELS = {"quy": "facebook/mms-tts-quy"}


def main() -> None:
    import torch
    from transformers import AutoTokenizer, VitsModel

    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="quy")
    parser.add_argument("--only-concrete", action="store_true")
    args = parser.parse_args()
    lang = args.lang

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(TTS_MODELS[lang])
    tts = VitsModel.from_pretrained(TTS_MODELS[lang]).to(device).eval()
    sr = tts.config.sampling_rate
    out_dir = media_dir(lang) / "lexemes"
    out_dir.mkdir(exist_ok=True)
    torch.manual_seed(13)

    with SessionLocal.begin() as db:
        stmt = select(Lexeme).where(Lexeme.lang == lang, is_current(Lexeme), Lexeme.audio_path.is_(None))
        if args.only_concrete:
            stmt = stmt.where(Lexeme.is_concrete)
        lexemes = db.scalars(stmt).all()
        for n, lx in enumerate(lexemes, 1):
            inputs = tok(lx.lemma, return_tensors="pt").to(device)
            if inputs["input_ids"].shape[-1] == 0:
                continue  # sin caracteres pronunciables para el TTS
            with torch.no_grad():
                wav = tts(**inputs).waveform[0].cpu()
            name = re.sub(r"[^a-z0-9ñ]", "_", lx.lemma) + f"-{lx.id}.ogg"
            encode_opus(wav, sr, out_dir / name)
            # metadato derivado del pipeline, previo a la puesta en servicio
            lx.audio_path, lx.audio_origin = f"{lang}/lexemes/{name}", "synthetic"
            if n % 200 == 0:
                print(f"  {n}/{len(lexemes)}")
    print(f"[{lang}] audio generado para {len(lexemes)} lemas → {out_dir}")


if __name__ == "__main__":
    main()
