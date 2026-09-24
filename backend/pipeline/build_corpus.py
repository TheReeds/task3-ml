"""Construcción del corpus provisional con audio y alineación por palabra (§9.3, pasos 1–3).

Mientras no llegue el corpus del curso:
  texto + traducción  ← AmericasNLP 2021 dev (quy–es, curado)
  audio               ← síntesis MMS-TTS (marcado audio_origin = "synthetic")
  marcas temporales   ← alineación forzada CTC con MMS_FA

Cuando llegue el corpus real con audio, se omite la síntesis y se reutiliza `align_tokens`.

Salida: data/processed/corpus/<lang>/entries.jsonl y data/media/<lang>/*.ogg
Uso:    uv run python -m pipeline.build_corpus [--limit N]
"""

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass

from pipeline.common import corpus_dir, media_dir, read_lines

LANG = "quy"
TTS_MODEL = "facebook/mms-tts-quy"
MIN_WORDS, MAX_WORDS = 4, 20


@dataclass
class TimedToken:
    token: str
    start_ms: int
    end_ms: int
    aligned: bool


def alignable_form(token: str, charset: set[str]) -> str:
    """Forma del token que entiende el alineador (minúsculas, solo letras de su alfabeto)."""
    t = token.lower().replace("ñ", "n")
    t = re.sub(r"[áàä]", "a", t)
    t = re.sub(r"[éèë]", "e", t)
    t = re.sub(r"[íìï]", "i", t)
    t = re.sub(r"[óòö]", "o", t)
    t = re.sub(r"[úùü]", "u", t)
    return "".join(c for c in t if c in charset)


def fill_unaligned(
    tokens: list[str], spans: list[tuple[int, int] | None], duration_ms: int
) -> list[TimedToken]:
    """Asigna tiempos a los tokens que el alineador no pudo procesar (números, signos).

    Heredan el hueco entre el token alineado anterior y el siguiente, de modo que el resaltado
    avanza de forma monótona sin saltarse ningún token mostrado.
    """
    out: list[TimedToken] = []
    for i, (tok, span) in enumerate(zip(tokens, spans, strict=True)):
        if span is not None:
            out.append(TimedToken(tok, span[0], span[1], True))
            continue
        prev_end = out[-1].end_ms if out else 0
        next_start = next((s[0] for s in spans[i + 1 :] if s is not None), duration_ms)
        out.append(TimedToken(tok, prev_end, max(prev_end, next_start), False))
    return out


class Aligner:
    """Alineación forzada por palabra con torchaudio MMS_FA."""

    def __init__(self, device: str) -> None:
        import torchaudio

        self.bundle = torchaudio.pipelines.MMS_FA
        self.model = self.bundle.get_model().to(device).eval()
        self.charset = set(self.bundle.get_dict()) - {"-", "*"}
        self.tokenizer = self.bundle.get_tokenizer()
        self.aligner = self.bundle.get_aligner()
        self.device = device

    def align_tokens(self, wav, sample_rate: int, tokens: list[str]) -> list[TimedToken]:
        import torch
        import torchaudio

        wav16 = torchaudio.functional.resample(wav, sample_rate, self.bundle.sample_rate)
        duration_ms = int(wav16.shape[-1] / self.bundle.sample_rate * 1000)
        forms = [alignable_form(t, self.charset) for t in tokens]
        idx = [i for i, f in enumerate(forms) if f]
        spans: list[tuple[int, int] | None] = [None] * len(tokens)
        if idx:
            with torch.no_grad():
                emission, _ = self.model(wav16.reshape(1, -1).to(self.device))
            word_spans = self.aligner(emission[0], self.tokenizer([forms[i] for i in idx]))
            ms_per_frame = duration_ms / emission.shape[1]
            for i, ws in zip(idx, word_spans, strict=True):
                spans[i] = (round(ws[0].start * ms_per_frame), round(ws[-1].end * ms_per_frame))
        return fill_unaligned(tokens, spans, duration_ms)


def encode_opus(wav, sample_rate: int, dest) -> None:
    """Codifica a Ogg/Opus (~10 KB por enunciado) para que Radio arranque rápido."""
    pcm = (wav.clamp(-1, 1) * 32767).short().numpy().tobytes()
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(sample_rate), "-ac", "1",
         "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", str(dest)],
        input=pcm, check=True,
    )


def main() -> None:
    import torch
    from transformers import AutoTokenizer, VitsModel

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    quy, es = read_lines("americasnlp/dev.quy"), read_lines("americasnlp/dev.es")
    pairs = [
        (i, q.strip(), e.strip())
        for i, (q, e) in enumerate(zip(quy, es, strict=True))
        if MIN_WORDS <= len(q.split()) <= MAX_WORDS
    ][: args.limit]

    tts_tok = AutoTokenizer.from_pretrained(TTS_MODEL)
    tts = VitsModel.from_pretrained(TTS_MODEL).to(device).eval()
    sr = tts.config.sampling_rate
    aligner = Aligner(device)
    audio_out = media_dir(LANG)
    torch.manual_seed(13)  # la síntesis VITS es estocástica

    rows = []
    for n, (line_no, text, translation) in enumerate(pairs, 1):
        with torch.no_grad():
            wav = tts(**tts_tok(text, return_tensors="pt").to(device)).waveform[0].cpu()
        tokens = text.split()
        timed = aligner.align_tokens(wav, sr, tokens)
        audio_name = f"americasnlp-dev-{line_no:04d}.ogg"
        encode_opus(wav, sr, audio_out / audio_name)
        rows.append({
            "source": "americasnlp-2021-dev",
            "source_ref": str(line_no),
            "text": text,
            "translation": translation,
            "audio_path": f"{LANG}/{audio_name}",
            "audio_origin": "synthetic",
            "speaker": "mms-tts-quy",
            "duration_ms": round(wav.shape[-1] / sr * 1000),
            "tokens": [asdict(t) for t in timed],
        })
        if n % 100 == 0:
            print(f"  {n}/{len(pairs)}")

    out = corpus_dir(LANG) / "entries.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    unaligned = sum(not t["aligned"] for r in rows for t in r["tokens"])
    total = sum(len(r["tokens"]) for r in rows)
    print(f"entries: {len(rows)} → {out} · tokens sin alinear: {unaligned}/{total}")


if __name__ == "__main__":
    main()
