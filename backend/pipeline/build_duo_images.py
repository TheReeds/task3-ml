"""Catálogo de imágenes para Dúo (§6.6).

Para cada concepto concreto con lema atestiguado en el corpus se buscan candidatas con licencia
libre en Wikimedia Commons (se guarda autor y licencia para la atribución). La búsqueda por texto
es ruidosa ("bread loaf" devuelve un edificio), así que CLIP filtra: cada imagen se clasifica
contra todos los conceptos y solo se conserva si la asigna al suyo con confianza suficiente.
Los vectores CLIP alimentan además la selección de distractores por similitud.

Uso: uv run python -m pipeline.build_duo_images [--lang quy] [--per-concept 4] [--candidates 10]
"""

import argparse
import hashlib
import html
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import DuoImage, DuoRound, Embedding, Lexeme
from app.services.corpus import is_current
from pipeline.common import media_dir

CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_ID = "clip-vit-b32"
USER_AGENT = "CorpusVivo/0.1 (proyecto academico, Universidad Peruana Union)"
API = "https://commons.wikimedia.org/w/api.php"
FREE_LICENSES = re.compile(r"^(CC0|CC BY(-SA)? [0-9.]+|Public domain|PD.*)$", re.I)
BAD_TITLES = re.compile(r"map|diagram|logo|drawing|icon|chart|coat of arms|flag|svg|scheme|plan", re.I)

# lema → (concepto en español, nombre en inglés para CLIP, búsqueda en Commons)
CONCEPTS = {
    "runa": ("persona", "a person", "portrait man Peru"),
    "warmi": ("mujer", "a woman", "woman portrait Andes"),
    "wawa": ("niño", "a child", "child portrait Peru"),
    "wasi": ("casa", "a house", "adobe house Peru"),
    "qullqi": ("dinero", "money", "coins banknotes money"),
    "nina": ("fuego", "fire", "campfire flames"),
    "killa": ("luna", "the moon", "full moon"),
    "maki": ("mano", "a hand", "human hand"),
    "yaku": ("agua", "water", "water stream"),
    "uma": ("cabeza", "a human head", "human head photograph"),
    "ñan": ("camino", "a dirt road", "dirt road Andes"),
    "para": ("lluvia", "rain", "rain falling"),
    "sacha": ("árbol", "a tree", "single tree"),
    "qucha": ("lago", "a lake", "Lake Titicaca"),
    "urqu": ("cerro", "a mountain", "Andes mountain"),
    "sara": ("maíz", "corn cobs", "maize corn cobs"),
    "mayu": ("río", "a river", "river Peru"),
    "ñawi": ("ojo", "a human eye", "human eye macro"),
    "rumi": ("piedra", "a rock", "boulder rock"),
    "inti": ("sol", "the sun", "sun sky sunset"),
    "tanta": ("pan", "bread", "bread bakery"),
    "punku": ("puerta", "a door", "wooden door"),
    "chakra": ("chacra", "a farm field", "farm field Peru"),
    "chaki": ("pie", "a human foot", "human foot barefoot"),
    "challwa": ("pescado", "a fish", "trout fish"),
    "puyu": ("nube", "clouds", "cumulus clouds"),
    "tiyana": ("silla", "a chair", "wooden chair"),
    "wayta": ("flor", "a flower", "flower blossom"),
    "papa": ("papa", "potatoes", "potatoes"),
    "piluta": ("pelota", "a ball", "football ball"),
    "riti": ("hielo", "ice and snow", "glacier ice snow"),
    "kiru": ("diente", "teeth", "human teeth"),
    "allqu": ("perro", "a dog", "dog"),
    "puyñu": ("cántaro", "a clay pot", "clay pot pottery"),
    "misi": ("gato", "a cat", "domestic cat"),
    "wallpa": ("gallina", "a chicken", "hen chicken"),
    "kuchi": ("cerdo", "a pig", "domestic pig"),
    "quwi": ("cuy", "a guinea pig", "guinea pig"),
    "llama": ("llama", "a llama", "llama animal"),
    "chita": ("oveja", "a sheep", "sheep"),
    "pisqu": ("pájaro", "a bird", "bird on branch"),
    "karru": ("auto", "a car", "car"),
    "yura": ("planta", "a potted plant", "potted plant"),
}


def _fetch(url: str, timeout: int, retries: int = 4) -> bytes:
    """GET con reintentos que respetan Retry-After ante HTTP 429/5xx."""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if attempt == retries or e.code not in (429, 500, 502, 503, 504):
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 5 * 2**attempt
            print(f"    HTTP {e.code}; reintento en {wait} s")
            time.sleep(min(wait, 120))
    raise RuntimeError("inalcanzable")


def api_get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    return json.loads(_fetch(url, timeout=30))


def search_images(query: str, limit: int) -> list[dict]:
    data = api_get({
        "action": "query", "generator": "search", "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": limit * 4, "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": 480,
    })
    out = []
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    for p in pages:
        ii = p["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        license_ = meta.get("LicenseShortName", {}).get("value", "")
        if ii.get("mime") not in ("image/jpeg", "image/png") or BAD_TITLES.search(p["title"]):
            continue
        if not FREE_LICENSES.match(license_.strip()):
            continue
        author = html.unescape(re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", ""))).strip()[:255]
        out.append({"thumb": ii["thumburl"], "page": ii["descriptionurl"], "license": license_,
                    "author": author or None})
        if len(out) == limit:
            break
    return out


def download(url: str) -> bytes:
    return _fetch(url, timeout=60)


def main() -> None:
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor

    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="quy")
    parser.add_argument("--per-concept", type=int, default=4)
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--min-prob", type=float, default=0.5)
    args = parser.parse_args()
    lang = args.lang

    with SessionLocal() as db:
        attested = set(db.scalars(select(Lexeme.lemma).where(
            Lexeme.lang == lang, is_current(Lexeme), Lexeme.frequency > 0)))
    concepts = {k: v for k, v in CONCEPTS.items() if k in attested}
    print(f"conceptos con lema atestiguado: {len(concepts)}/{len(CONCEPTS)}")

    out_dir = media_dir(lang).parent / "duo"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Manifiesto local de búsquedas: las re-ejecuciones no vuelven a consultar la API
    manifest_path = out_dir / f"manifest-{args.candidates}.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    records, images = [], []
    for lemma, (concept_es, _en, query) in concepts.items():
        if lemma in manifest:
            found = manifest[lemma]
        else:
            try:
                found = search_images(query, args.candidates)
            except OSError as e:
                print(f"  {lemma}: error de red ({e}); se omite")
                continue
            manifest[lemma] = found
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
            time.sleep(1.0)
        for img in found:
            # nombre derivado de la URL: la caché nunca desalinea imagen y atribución
            name = f"{lemma}-{hashlib.sha1(img['thumb'].encode()).hexdigest()[:10]}.jpg"
            cached = out_dir / name
            try:
                if cached.exists():  # re-ejecuciones: no se vuelve a descargar
                    pil = Image.open(cached).convert("RGB")
                else:
                    pil = Image.open(io.BytesIO(download(img["thumb"]))).convert("RGB")
                    pil.save(cached, "JPEG", quality=85)
                    time.sleep(0.2)  # cortesía con la API de Wikimedia
            except (OSError, ValueError):
                continue
            records.append({"lang": lang, "concept_lemma": lemma, "concept_es": concept_es,
                            "file_path": f"duo/{name}", "source_url": img["page"],
                            "author": img["author"], "license": img["license"]})
            images.append(pil)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(CLIP_MODEL).to(device).eval()
    proc = CLIPProcessor.from_pretrained(CLIP_MODEL)

    def as_tensor(out):  # transformers ≥ 5 devuelve un objeto; la proyección está en pooler_output
        return out if isinstance(out, torch.Tensor) else out.pooler_output

    vecs = []
    for i in range(0, len(images), 32):
        inputs = proc(images=images[i : i + 32], return_tensors="pt").to(device)
        with torch.no_grad():
            feats = as_tensor(model.get_image_features(**inputs))
        vecs.append(torch.nn.functional.normalize(feats, dim=-1).cpu())
    img_vecs = torch.cat(vecs)

    # Clasificación zero-shot contra todos los conceptos como filtro de calidad
    lemmas = list(concepts)
    prompts = [f"a photo of {concepts[lm][1]}" for lm in lemmas]
    with torch.no_grad():
        t = proc(text=prompts, return_tensors="pt", padding=True).to(device)
        txt = torch.nn.functional.normalize(as_tensor(model.get_text_features(**t)), dim=-1).cpu()
    probs = (100 * img_vecs @ txt.T).softmax(dim=-1)
    kept_idx = []
    for lm in lemmas:
        own = lemmas.index(lm)
        cands = [i for i, r in enumerate(records) if r["concept_lemma"] == lm
                 and probs[i].argmax().item() == own and probs[i, own].item() >= args.min_prob]
        cands.sort(key=lambda i: -probs[i, own].item())
        kept_idx += cands[: args.per_concept]
        total = sum(r["concept_lemma"] == lm for r in records)
        print(f"  {lm} ({concepts[lm][0]}): {len(cands[: args.per_concept])} de {total} candidatas")
    records = [records[i] for i in kept_idx]
    vecs = img_vecs[kept_idx].numpy()
    by_concept = {}
    for r in records:
        by_concept[r["concept_lemma"]] = by_concept.get(r["concept_lemma"], 0) + 1

    with SessionLocal.begin() as db:
        old_ids = select(DuoImage.id).where(DuoImage.lang == lang)
        db.execute(delete(Embedding).where(Embedding.owner_type == "image", Embedding.owner_id.in_(old_ids)))
        # Las imágenes usadas en rondas se conservan inactivas; las demás se eliminan
        used = set(db.scalars(select(DuoRound.target_image_id)))
        for (opts,) in db.execute(select(DuoRound.option_ids)):
            used.update(opts)
        for img in db.scalars(select(DuoImage).where(DuoImage.lang == lang)):
            if img.id in used:
                img.active = False
            else:
                db.delete(img)
        for rec, vec in zip(records, vecs, strict=True):
            img = DuoImage(**rec, active=True)
            db.add(img)
            db.flush()
            db.add(Embedding(owner_type="image", owner_id=img.id, model=CLIP_ID, vector=vec))
    print(f"[{lang}] catálogo Dúo: {len(records)} imágenes de {len(by_concept)} conceptos → {out_dir}")


if __name__ == "__main__":
    main()
