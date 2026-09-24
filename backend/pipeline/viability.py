"""Fase 0 — verificación de supuestos técnicos con modelos públicos (quechua).

Cada sección responde una pregunta del informe de viabilidad (doc. técnico §11.1):
  translate  ¿NLLB-200 traduce quy<->es de forma utilizable?          (Radio, contrato §10.2)
  align      ¿La alineación forzada MMS da marcas por palabra creíbles? (Radio, resaltado)
  embed      ¿Qué vectores dan vecindarios semánticos coherentes?       (Radar)
  lexicon    ¿Cuántos lemas frecuentes hay para la palabra del día?    (Radar)

Uso: uv run python -m pipeline.viability [translate|align|embed|lexicon ...]
Los resultados se escriben en data/processed/viability/<seccion>.md
"""

import re
import sys
import time
from collections import Counter
from pathlib import Path

from pipeline.quechua import lemmatize, normalize, tokenize

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "viability"

NLLB = "facebook/nllb-200-distilled-600M"
TTS = "facebook/mms-tts-quy"

# Palabras de prueba para inspeccionar vecindarios semánticos (Radar).
PROBES = [
    "wasi",
    "yaku",
    "mikuy",
    "runa",
    "allqu",
    "inti",
    "tayta",
    "mama",
    "urqu",
    "sara",
    "killa",
    "puñuy",
]


def read_lines(rel: str) -> list[str]:
    return (RAW / rel).read_text(encoding="utf-8-sig").splitlines()


def load_dictionary() -> dict[str, str]:
    """Lemas de una palabra del diccionario AmericasNLP, normalizados → glosa en español."""
    quy = [q.strip().strip(" .").lower() for q in read_lines("americasnlp/dict.quy")]
    es = [e.strip().strip(" .") for e in read_lines("americasnlp/dict.es")]
    return {normalize(q): e for q, e in zip(quy, es) if len(q.split()) == 1 and len(q) >= 3}


def write_report(name: str, lines: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n→ {path.relative_to(ROOT)}")


def section_translate(n: int = 200) -> None:
    import sacrebleu
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    quy, es = read_lines("americasnlp/dev.quy")[:n], read_lines("americasnlp/dev.es")[:n]
    tok = AutoTokenizer.from_pretrained(NLLB)
    model = AutoModelForSeq2SeqLM.from_pretrained(NLLB, torch_dtype=torch.float16).cuda().eval()

    def translate(texts: list[str], src: str, tgt: str) -> list[str]:
        tok.src_lang = src
        out = []
        for i in range(0, len(texts), 16):
            batch = tok(texts[i : i + 16], return_tensors="pt", padding=True, truncation=True).to(
                "cuda"
            )
            with torch.no_grad():
                gen = model.generate(
                    **batch,
                    forced_bos_token_id=tok.convert_tokens_to_ids(tgt),
                    max_new_tokens=200,
                    max_length=None,
                )
            out += tok.batch_decode(gen, skip_special_tokens=True)
        return out

    t0 = time.time()
    hyp_es = translate(quy, "quy_Latn", "spa_Latn")
    t_q2e = time.time() - t0
    t0 = time.time()
    hyp_quy = translate(es, "spa_Latn", "quy_Latn")
    t_e2q = time.time() - t0

    chrf_q2e = sacrebleu.corpus_chrf(hyp_es, [es], word_order=2).score
    chrf_e2q = sacrebleu.corpus_chrf(hyp_quy, [quy], word_order=2).score
    vram = torch.cuda.max_memory_allocated() / 2**30

    lines = [
        "# Traducción — NLLB-200 distilled 600M (fp16, GPU)",
        "",
        f"Muestra: {n} oraciones del dev de AmericasNLP 2021.",
        "",
        "| Dirección | chrF++ | Tiempo | ",
        "|---|---|---|",
        f"| quy → es | {chrf_q2e:.1f} | {t_q2e:.1f} s |",
        f"| es → quy | {chrf_e2q:.1f} | {t_e2q:.1f} s |",
        "",
        f"VRAM pico: {vram:.2f} GB",
        "",
        "Referencia: el baseline oficial de AmericasNLP 2021 para es→quy rondaba chrF ~30.",
        "",
        "## Ejemplos",
    ]
    for i in range(5):
        lines += [
            "",
            f"- **quy:** {quy[i]}",
            f"  - ref es: {es[i]}",
            f"  - NLLB es: {hyp_es[i]}",
        ]
    write_report("translate", lines)


def section_align(n: int = 6) -> None:
    import soundfile as sf
    import torch
    import torchaudio
    from transformers import AutoTokenizer, VitsModel

    sents = [s for s in read_lines("americasnlp/dev.quy") if 5 <= len(s.split()) <= 14][:n]
    audio_dir = OUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # 1) Audio sintético con MMS-TTS (sustituye al audio real mientras no llegue el corpus).
    tts_tok = AutoTokenizer.from_pretrained(TTS)
    tts = VitsModel.from_pretrained(TTS).cuda().eval()
    wavs = []
    for i, s in enumerate(sents):
        inputs = tts_tok(s, return_tensors="pt").to("cuda")
        with torch.no_grad():
            wav = tts(**inputs).waveform[0].cpu()
        sr = tts.config.sampling_rate
        sf.write(audio_dir / f"sample_{i}.wav", wav.numpy(), sr)
        wavs.append((wav, sr))
    del tts
    torch.cuda.empty_cache()

    # 2) Alineación forzada por palabra con MMS_FA (CTC).
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model().cuda().eval()
    dictionary = bundle.get_dict()
    aligner = bundle.get_aligner()
    tokenizer = bundle.get_tokenizer()

    lines = [
        "# Alineación forzada — MMS-TTS (quy) + MMS_FA",
        "",
        "Audio generado por síntesis; la alineación se calcula sin conocer los tiempos del TTS.",
        "",
    ]
    stats = []
    for i, ((wav, sr), s) in enumerate(zip(wavs, sents)):
        words = [w for w in (re.sub(r"[^a-zñ' ]", " ", s.lower().replace("ñ", "n")).split()) if w]
        words = [w.replace("'", "") for w in words]
        words = [w for w in words if all(c in dictionary for c in w)]
        wav16 = torchaudio.functional.resample(wav, sr, bundle.sample_rate).unsqueeze(0).cuda()
        with torch.no_grad():
            emission, _ = model(wav16)
        spans = aligner(emission[0], tokenizer(words))
        ratio = wav16.shape[1] / emission.shape[1] / bundle.sample_rate
        timed = [(w, sp[0].start * ratio, sp[-1].end * ratio) for w, sp in zip(words, spans)]
        dur = wav16.shape[1] / bundle.sample_rate
        coverage = (timed[-1][2] - timed[0][1]) / dur
        monotonic = all(a[2] <= b[1] + 1e-3 for a, b in zip(timed, timed[1:]))
        stats.append((coverage, monotonic, min(e - b for _, b, e in timed)))
        lines += [f"## sample_{i}.wav ({dur:.2f} s)", "", f"> {s}", ""]
        lines += [" · ".join(f"`{w}` {b:.2f}–{e:.2f}" for w, b, e in timed), ""]

    lines += [
        "## Resumen",
        "",
        f"- Cobertura media del audio por palabras: {sum(c for c, _, _ in stats) / len(stats):.0%}",
        f"- Enunciados con marcas monótonas: {sum(m for _, m, _ in stats)}/{len(stats)}",
        f"- Duración mínima de palabra: {min(d for _, _, d in stats) * 1000:.0f} ms",
    ]
    write_report("align", lines)


def load_vec(path: Path, limit: int | None = None) -> dict:
    import numpy as np

    vecs = {}
    with path.open(encoding="utf-8", errors="ignore") as f:
        next(f)
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            parts = line.rstrip().split(" ")
            if len(parts) < 10:
                continue
            vecs[parts[0]] = np.asarray(parts[1:], dtype=np.float32)
    return vecs


def section_embed() -> None:
    import numpy as np
    from gensim.models import FastText

    corpus = [
        tokenize(s) for s in read_lines("americasnlp/train.quy") + read_lines("americasnlp/dev.quy")
    ]
    freq = Counter(w for s in corpus for w in s)

    lines = ["# Representaciones vectoriales para Radar", ""]

    def neighbors(get, vocab_words, mat, word, k=8):
        v = get(word)
        if v is None:
            return "—(sin vector)"
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = mat @ v
        idx = np.argsort(-sims)[: k + 1]
        return ", ".join(vocab_words[j] for j in idx if vocab_words[j] != word)[:200]

    # A) fastText Wikipedia (wiki.qu)
    wiki = load_vec(RAW / "fasttext/wiki.qu.vec")
    cand = [w for w, c in freq.most_common(20000) if w in wiki]
    mat = np.stack([wiki[w] for w in cand])
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    top5k = [w for w, _ in freq.most_common(5000)]
    cov = sum(w in wiki for w in top5k) / len(top5k)
    lines += [
        "## A) fastText wiki.qu (preentrenado)",
        "",
        f"Vocabulario: {len(wiki):,} · cobertura de las 5.000 palabras más frecuentes del corpus: {cov:.0%}",
        "",
    ]
    lines += [f"- **{p}** → {neighbors(wiki.get, cand, mat, p)}" for p in PROBES]

    # B) FastText entrenado sobre el corpus (subpalabras: útil para una lengua aglutinante)
    t0 = time.time()
    ft = FastText(
        corpus,
        vector_size=200,
        window=5,
        min_count=3,
        sg=1,
        epochs=10,
        workers=12,
        min_n=3,
        max_n=6,
    )
    cand = [w for w, c in freq.most_common(20000) if c >= 3]
    mat = np.stack([ft.wv[w] for w in cand])
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    lines += [
        "",
        f"## B) FastText entrenado sobre AmericasNLP train+dev ({time.time() - t0:.0f} s)",
        "",
        f"Vocabulario: {len(ft.wv):,}",
        "",
    ]
    lines += [f"- **{p}** → {neighbors(lambda w: ft.wv[w], cand, mat, p)}" for p in PROBES]

    # C) Igual que B, pero con ortografía normalizada y formas flexionadas reducidas a su lema
    lemmas = load_dictionary()
    lem_corpus = [[lemmatize(normalize(w), lemmas) or normalize(w) for w in s] for s in corpus]
    lfreq = Counter(w for s in lem_corpus for w in s)
    t0 = time.time()
    ftl = FastText(
        lem_corpus,
        vector_size=200,
        window=5,
        min_count=3,
        sg=1,
        epochs=10,
        workers=12,
        min_n=3,
        max_n=6,
    )
    cand = [w for w in lemmas if lfreq[w] >= 5]
    mat = np.stack([ftl.wv[w] for w in cand])
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    lines += [
        "",
        f"## C) FastText a nivel de lema, ortografía normalizada ({time.time() - t0:.0f} s)",
        "",
        f"Espacio de búsqueda: {len(cand):,} lemas del diccionario con frecuencia ≥ 5",
        "",
    ]
    lines += [
        f"- **{p}** ({lemmas.get(p, '?')}) → "
        + ", ".join(
            f"{w} ({lemmas[w]})" for w in neighbors(lambda w: ftl.wv[w], cand, mat, p).split(", ")
        )
        for p in PROBES
    ]

    write_report("embed", lines)


def section_lexicon() -> None:
    corpus = read_lines("americasnlp/train.quy") + read_lines("americasnlp/dev.quy")
    freq = Counter(w for s in corpus for w in tokenize(s))
    entries = list(zip(read_lines("americasnlp/dict.quy"), read_lines("americasnlp/dict.es")))
    single = {
        q.strip(" .").lower(): e.strip(" .") for q, e in entries if len(q.strip(" .").split()) == 1
    }

    lines = [
        "# Léxico — diccionario AmericasNLP vs. frecuencias del corpus",
        "",
        f"Entradas del diccionario: {len(entries):,} · de una sola palabra: {len(single):,}",
        f"Tipos distintos en el corpus: {len(freq):,} · tokens: {sum(freq.values()):,}",
        "",
        "| Umbral de frecuencia | Lemas del diccionario atestiguados |",
        "|---|---|",
    ]
    for th in (1, 5, 20, 50, 100):
        lines.append(f"| ≥ {th} | {sum(freq[w] >= th for w in single):,} |")
    lemmas = load_dictionary()
    lfreq = Counter(lemmatize(normalize(w), lemmas) for s in corpus for w in tokenize(s))
    lines += [
        "",
        "Tras normalizar ortografía y reducir formas flexionadas a su lema:",
        "",
        "| Umbral de frecuencia | Lemas atestiguados |",
        "|---|---|",
    ]
    for th in (1, 5, 20, 50, 100):
        lines.append(f"| ≥ {th} | {sum(lfreq[w] >= th for w in lemmas):,} |")
    top = sorted(((freq[w], w) for w in single if freq[w] >= 50), reverse=True)[:40]
    lines += ["", "Muestra de candidatos a palabra del día (freq ≥ 50):", ""]
    lines.append(", ".join(f"{w} ({single[w]})" for _, w in top))
    write_report("lexicon", lines)


SECTIONS = {
    "translate": section_translate,
    "align": section_align,
    "embed": section_embed,
    "lexicon": section_lexicon,
}

if __name__ == "__main__":
    for name in sys.argv[1:] or SECTIONS:
        print(f"\n===== {name} =====")
        SECTIONS[name]()
