"""Temas automáticos para las emisoras de Radio (doc. técnico, tabla 7).

El corpus provisional no trae dominio temático, así que se agrupan las entradas por el
significado de su traducción al español:
  1. vector de cada traducción con un modelo multilingüe de oraciones (media de tokens);
  2. k-means (k++ con reinicios) eligiendo k por silueta, con un tamaño mínimo por tema;
  3. nombre y palabras clave por tema según TF-IDF de clase frente al resto.

Los temas se guardan en data/processed/corpus/<lang>/topics.json para aplicarlos a cualquier
base (local o Neon) sin recalcular. Para renombrar temas, editar "name" en ese archivo y volver
a aplicar con --apply-only (los nombres actuales se revisaron a mano leyendo muestras).

Limitación: con el corpus provisional la estructura temática es débil (silueta ≈ 0,04); algunos
grupos son temáticos (dinero, escuela) y otros reúnen frases por estilo (relatos, charla). Con
el corpus real, si trae dominios, se usan esos y este paso no hace falta.

Uso: uv run python -m pipeline.build_topics [--lang quy] [--apply-only]
"""

import argparse
import json
import re
import unicodedata
from collections import Counter

import numpy as np
from sqlalchemy import delete, select, update

from app.db import SessionLocal
from app.models import Entry, Topic, Translation
from app.services.corpus import is_current
from pipeline.common import corpus_dir

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
K_RANGE = range(6, 13)
MIN_TOPIC_SIZE = 30
SEED = 13

STOPWORDS = set("""a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque bajo bien
cada casi como con contra cual cuales cuando cuanto de del desde donde dos durante e el ella ellas
ello ellos en entre era eran es esa esas ese eso esos esta estaba estado estan estar este esto estos
fue fueron gran ha hace hacer hacia han hasta hay he la las le les lo los mas me mi mis mucho muchos
muy nada ni no nos nosotros nuestra nuestro o otra otras otro otros para pero poco por porque que
quien se ser si sido sin sobre solo son su sus tambien tan tanto te tener tengo tiene tienen todo
todos tu tus un una uno unos usted ustedes y ya yo puede pueden cosas vez veces tiempo ano anos dia
dias forma parte manera mismo misma lugar gente persona personas asi hizo hacen hecho debe deben
estoy estamos siempre nunca mejor menos tres cuatro cinco uno primera primer entonces luego despues
ademas mientras segun cual quiero quiere voy va van tuvo tenia hacia sera seria han habia ser
creo crees cree dijo dije dice decir digo nadie ningun ninguno ninguna absoluto contigo conmigo
osea vale bueno cosa algo alguien todas todavia realmente verdad solo sola ellos ellas nuestros
estas estaban estaria podria podemos puedo quiero queria quieres saber sabes necesito hablar
visto veo ver dejar dejo hablo toda nosotras ustedes haber hemos hubo tenemos tienes""".split())


def fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def embed(texts: list[str]) -> np.ndarray:
    import torch
    from transformers import AutoModel, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModel.from_pretrained(MODEL).to(device).eval()
    out = []
    for i in range(0, len(texts), 64):
        batch = tok(texts[i : i + 64], padding=True, truncation=True, max_length=128,
                    return_tensors="pt").to(device)
        with torch.no_grad():
            hidden = model(**batch).last_hidden_state
        mask = batch["attention_mask"].unsqueeze(-1).float()
        vec = (hidden * mask).sum(1) / mask.sum(1)
        out.append(torch.nn.functional.normalize(vec, dim=-1).cpu().numpy())
    return np.concatenate(out)


def kmeans(x: np.ndarray, k: int, rng: np.random.Generator, iters: int = 100) -> np.ndarray:
    centers = [x[rng.integers(len(x))]]
    for _ in range(1, k):  # k-means++
        d = np.min([((x - c) ** 2).sum(1) for c in centers], axis=0)
        centers.append(x[rng.choice(len(x), p=d / d.sum())])
    centers = np.array(centers)
    labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        new = np.argmin(((x[:, None, :] - centers[None]) ** 2).sum(-1), axis=1)
        if (new == labels).all():
            break
        labels = new
        centers = np.array([x[labels == j].mean(0) if (labels == j).any() else centers[j] for j in range(k)])
    return labels


def silhouette(x: np.ndarray, labels: np.ndarray) -> float:
    d = np.sqrt(np.maximum(((x[:, None, :] - x[None]) ** 2).sum(-1), 0))
    scores = []
    for i in range(len(x)):
        same = labels == labels[i]
        if same.sum() < 2:
            continue
        a = d[i, same].sum() / (same.sum() - 1)
        b = min(d[i, labels == j].mean() for j in set(labels) if j != labels[i])
        scores.append((b - a) / max(a, b))
    return float(np.mean(scores))


def best_partition(x: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    best, best_score = None, -1.0
    for k in K_RANGE:
        for _ in range(5):  # reinicios
            labels = kmeans(x, k, rng)
            if np.bincount(labels, minlength=k).min() < MIN_TOPIC_SIZE:
                continue
            score = silhouette(x, labels)
            if score > best_score:
                best, best_score = labels, score
        print(f"  k={k}: mejor silueta acumulada {best_score:.3f}")
    if best is None:
        raise SystemExit("Ninguna partición cumple el tamaño mínimo por tema")
    return best


def keywords(texts: list[str], labels: np.ndarray, top: int = 5) -> dict[int, list[str]]:
    docs = {j: Counter() for j in set(labels)}
    for t, j in zip(texts, labels, strict=True):
        docs[j].update(w for w in re.findall(r"[a-zñ]{4,}", fold(t)) if w not in STOPWORDS)
    df = Counter(w for c in docs.values() for w in c)
    n = len(docs)
    sizes = Counter(labels.tolist())
    out = {}
    for j, c in docs.items():
        total = sum(c.values()) or 1
        # palabra presente en al menos el 4 % de las frases del tema (evita nombres propios sueltos)
        frequent = [w for w in c if c[w] >= max(3, 0.04 * sizes[j])]
        scored = sorted(frequent, key=lambda w: -(c[w] / total) * np.log(1 + n / df[w]))
        out[j] = scored[:top]
    return out


def compute(lang: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(
            select(Entry.id, Entry.source_ref, Translation.text)
            .join(Translation, Translation.entry_id == Entry.id)
            .where(Entry.lang == lang, is_current(Entry), is_current(Translation))
            .order_by(Entry.id)
        ).all()
    refs = [r.source_ref for r in rows]
    texts = [r.text for r in rows]
    print(f"entradas: {len(texts)}")
    labels = best_partition(embed(texts))
    kw = keywords(texts, labels)
    topics = []
    for j in sorted(set(labels)):
        words = kw[j]
        members = [refs[i] for i in np.flatnonzero(labels == j)]
        if not words:
            # grupo sin palabras de contenido recurrentes: agrupa por forma, no por tema
            slug, name = "variado", "Temas variados"
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", words[0])[:40]
            name = f"{words[0].capitalize()} y {words[1]}" if len(words) > 1 else words[0].capitalize()
        if any(t["slug"] == slug for t in topics):
            slug = f"{slug}-{j}"
        topics.append({"slug": slug, "name": name, "keywords": words,
                       "source_refs": members})
        print(f"  {slug:>14} ({len(members):3d}): {', '.join(words)}")
    return topics


def apply(lang: str, topics: list[dict]) -> None:
    with SessionLocal.begin() as db:
        db.execute(delete(Topic).where(Topic.lang == lang))
        db.execute(update(Entry).where(Entry.lang == lang).values(domain=None))
        for t in topics:
            db.add(Topic(lang=lang, slug=t["slug"], name=t["name"], keywords=t["keywords"],
                         method="clustering"))
            # metadato derivado del pipeline: aplica a todas las versiones de la entrada
            db.execute(update(Entry).where(Entry.lang == lang, Entry.source_ref.in_(t["source_refs"]))
                       .values(domain=t["slug"]))
    print(f"[{lang}] {len(topics)} temas aplicados")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="quy")
    parser.add_argument("--apply-only", action="store_true")
    args = parser.parse_args()
    path = corpus_dir(args.lang) / "topics.json"
    if args.apply_only:
        topics = json.loads(path.read_text(encoding="utf-8"))
    else:
        topics = compute(args.lang)
        path.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    apply(args.lang, topics)


if __name__ == "__main__":
    main()
