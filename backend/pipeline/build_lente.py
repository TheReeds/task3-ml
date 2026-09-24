"""Correspondencia entre etiquetas de visión y lemas para el módulo Lente (§6.5, §9.3 paso 6).

Para cada etiqueta del clasificador (COCO-SSD, 80 clases de objetos cotidianos):
  1. diccionario: búsqueda inversa de la etiqueta (y sinónimos en español) en las glosas;
  2. modelo: traducción es→lengua mediante el adaptador, reducida a lema, y validada con una
     traducción de vuelta lengua→es que debe coincidir con la etiqueta o un sinónimo;
y en ambos casos se exige que el lema esté atestiguado en el corpus (lexema vigente con
frecuencia > 0) y no sea una palabra funcional. Las etiquetas sin correspondencia válida
quedan como vacíos.

Debe ejecutarse después de `pipeline.ingest`.
Uso: uv run python -m pipeline.build_lente [--lang quy]
"""

import argparse
import re
import unicodedata
from collections import defaultdict

from sqlalchemy import delete, insert, select, update

from app.adapters import get_adapter
from app.db import SessionLocal
from app.models import Lexeme, VisionLabel
from app.nlp.quechua import lemmatize, normalize, tokenize
from app.services.corpus import is_current
from pipeline.common import read_lines

LABEL_SET = "coco-ssd"

# Etiqueta COCO → traducción principal y sinónimos en español (el primero se muestra al usuario)
COCO_SSD_ES: dict[str, list[str]] = {
    "person": ["persona", "hombre", "gente", "mujer"], "bicycle": ["bicicleta"],
    "car": ["auto", "carro", "coche"], "motorcycle": ["moto", "motocicleta"],
    "airplane": ["avión"], "bus": ["bus", "ómnibus"], "train": ["tren"], "truck": ["camión"],
    "boat": ["bote", "barco", "balsa"], "traffic light": ["semáforo"],
    "fire hydrant": ["hidrante"], "stop sign": ["señal de pare"], "parking meter": ["parquímetro"],
    "bench": ["banca", "banco", "asiento"], "bird": ["pájaro", "ave"], "cat": ["gato"],
    "dog": ["perro"], "horse": ["caballo"], "sheep": ["oveja"], "cow": ["vaca", "toro"],
    "elephant": ["elefante"], "bear": ["oso"], "zebra": ["cebra"], "giraffe": ["jirafa"],
    "backpack": ["mochila", "bolsa", "saco"], "umbrella": ["paraguas"],
    "handbag": ["bolso", "cartera", "bolsa"], "tie": ["corbata"], "suitcase": ["maleta"],
    "frisbee": ["disco volador"], "skis": ["esquís"], "snowboard": ["tabla de nieve"],
    "sports ball": ["pelota", "balón"], "kite": ["cometa"], "baseball bat": ["bate"],
    "baseball glove": ["guante"], "skateboard": ["patineta"], "surfboard": ["tabla de surf"],
    "tennis racket": ["raqueta"], "bottle": ["botella"], "wine glass": ["copa", "vaso"],
    "cup": ["taza", "vaso", "tazón"], "fork": ["tenedor"], "knife": ["cuchillo"],
    "spoon": ["cuchara"], "bowl": ["plato hondo", "tazón", "plato"], "banana": ["plátano"],
    "apple": ["manzana"], "sandwich": ["sándwich", "pan"], "orange": ["naranja"],
    "broccoli": ["brócoli"], "carrot": ["zanahoria"], "hot dog": ["salchicha"],
    "pizza": ["pizza"], "donut": ["rosquilla"], "cake": ["torta", "pastel"],
    "chair": ["silla", "asiento"], "couch": ["sofá"], "potted plant": ["planta", "maceta"],
    "bed": ["cama"], "dining table": ["mesa"], "toilet": ["inodoro", "baño"],
    "tv": ["televisor", "televisión"], "laptop": ["computadora", "laptop"],
    "mouse": ["ratón"], "remote": ["control remoto"], "keyboard": ["teclado"],
    "cell phone": ["celular", "teléfono"], "microwave": ["microondas"], "oven": ["horno"],
    "toaster": ["tostadora"], "sink": ["lavadero", "lavabo"], "refrigerator": ["refrigeradora"],
    "book": ["libro"], "clock": ["reloj"], "vase": ["florero", "jarrón", "cántaro"],
    "scissors": ["tijeras"], "teddy bear": ["peluche", "muñeco"], "hair drier": ["secadora"],
    "toothbrush": ["cepillo de dientes"],
}

ARTICLES = re.compile(r"^(el|la|los|las|un|una|unos|unas)\s+")


def norm_es(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower().strip())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\(.*?\)", "", t)
    return ARTICLES.sub("", t.strip(" .;:")).strip()


def gloss_index() -> dict[str, set[str]]:
    """Glosa en español (cada acepción separada por comas) → lemas quechuas normalizados."""
    index: dict[str, set[str]] = defaultdict(set)
    quy = read_lines("americasnlp/dict.quy")
    es = read_lines("americasnlp/dict.es")
    for q, e in zip(quy, es, strict=True):
        q = q.strip().strip(" .").lower()
        if len(q.split()) != 1:
            continue
        for sense in re.split(r"[,;/]", e):
            if key := norm_es(sense):
                index[key].add(normalize(q))
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="quy")
    args = parser.parse_args()
    lang = args.lang
    adapter = get_adapter()
    index = gloss_index()

    with SessionLocal.begin() as db:
        lexemes = db.scalars(
            select(Lexeme).where(Lexeme.lang == lang, is_current(Lexeme), Lexeme.frequency > 0,
                                 ~Lexeme.is_function_word)
        ).all()
        by_lemma = {lx.lemma: lx for lx in lexemes}

        # Traducciones del modelo para las etiquetas sin entrada de diccionario (en lote)
        pending = [lbl for lbl, syn in COCO_SSD_ES.items()
                   if not any(index.get(norm_es(s), set()) & by_lemma.keys() for s in syn)]
        model_out = dict(zip(pending, adapter.translate([COCO_SSD_ES[p][0] for p in pending], lang),
                             strict=True))

        # Candidatos del modelo y su traducción de vuelta (validación ida y vuelta)
        model_candidates: dict[str, str] = {}
        for label, out in model_out.items():
            for w in tokenize(out):
                if lemma := lemmatize(normalize(w), by_lemma):
                    model_candidates[label] = lemma
                    break
        back = dict(zip(model_candidates, adapter.translate_inverse(list(model_candidates.values()), lang),
                        strict=True))

        def round_trip_ok(label: str) -> bool:
            back_words = set(norm_es(back[label]).split())
            return any(set(norm_es(s).split()) <= back_words for s in COCO_SSD_ES[label])

        rows, concrete = [], set()
        for label, synonyms in COCO_SSD_ES.items():
            lexeme, method = None, None
            for syn in synonyms:
                attested = [by_lemma[q] for q in index.get(norm_es(syn), ()) if q in by_lemma]
                if attested:
                    lexeme, method = max(attested, key=lambda lx: lx.frequency), "dictionary"
                    break
            if lexeme is None and label in model_candidates and round_trip_ok(label):
                lexeme, method = by_lemma[model_candidates[label]], "model"
            if lexeme is not None:
                concrete.add(lexeme.id)
            rows.append({"label_set": LABEL_SET, "label": label, "label_es": synonyms[0], "lang": lang,
                         "lexeme_id": lexeme.id if lexeme else None, "method": method})

        db.execute(delete(VisionLabel).where(VisionLabel.lang == lang, VisionLabel.label_set == LABEL_SET,
                                             VisionLabel.method.is_distinct_from("community")))
        kept = set(db.scalars(select(VisionLabel.label).where(VisionLabel.lang == lang,
                                                              VisionLabel.label_set == LABEL_SET)))
        db.execute(insert(VisionLabel), [r for r in rows if r["label"] not in kept])
        concrete |= set(db.scalars(select(VisionLabel.lexeme_id).where(
            VisionLabel.lang == lang, VisionLabel.method == "community", VisionLabel.lexeme_id.is_not(None))))
        # metadato derivado del pipeline: lemas aptos para Lente
        db.execute(update(Lexeme).where(Lexeme.lang == lang).values(is_concrete=False))
        db.execute(update(Lexeme).where(Lexeme.id.in_(concrete)).values(is_concrete=True))

    mapped = [r for r in rows if r["lexeme_id"]]
    lemma_of = {lx.id: lx.lemma for lx in lexemes}
    print(f"[{lang}] {LABEL_SET}: {len(mapped)}/{len(rows)} etiquetas con lema "
          f"(diccionario {sum(r['method'] == 'dictionary' for r in rows)}, "
          f"modelo {sum(r['method'] == 'model' for r in rows)})")
    for label, lemma in model_candidates.items():
        verdict = "aceptado" if round_trip_ok(label) else "descartado"
        print(f"  modelo: {label} → {lemma} → «{back[label]}» ({verdict})")
    for r in mapped:
        print(f"  {r['label']:>15} ({r['label_es']}) → {lemma_of[r['lexeme_id']]} [{r['method']}]")


if __name__ == "__main__":
    main()
