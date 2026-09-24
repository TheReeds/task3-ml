"""Siembra de elementos de control para estimar la confiabilidad de revisores (§7.4).

Se generan automáticamente a partir del corpus, en pares equilibrados:
  expected=reject  el original es el dato del corpus y la propuesta un error deliberado
  expected=accept  el "original" mostrado es el error y la propuesta restaura el dato del corpus

Errores deliberados: letras intercambiadas o eliminadas en un token, traducción de otra
entrada, glosa de otro lema. El equipo puede añadir controles curados a mano con el mismo
formato. Los controles nunca se aplican al corpus.

Uso: uv run python -m pipeline.seed_gold [--lang quy] [--per-type 20] [--seed 7]
"""

import argparse
import random

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import Alignment, Contribution, Entry, GoldItem, Lexeme, Review, Translation
from app.services.corpus import is_current


def corrupt(token: str, rng: random.Random) -> str | None:
    """Error ortográfico plausible pero inequívoco para quien escucha el audio."""
    letters = [i for i, ch in enumerate(token) if ch.isalpha()]
    if len(letters) < 5:
        return None
    chars = list(token)
    i = rng.choice(letters[1:-2])
    if rng.random() < 0.5 and chars[i] != chars[i + 1]:
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
    else:
        del chars[i]
    out = "".join(chars)
    return out if out != token else None


def add_gold(db, lang, type_, target_type, target_id, payload, expected) -> None:
    c = Contribution(contributor_id=None, lang=lang, type=type_, target_type=target_type,
                     target_id=target_id, payload=payload, status="gold")
    db.add(c)
    db.flush()
    db.add(GoldItem(contribution_id=c.id, expected_verdict=expected))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="quy")
    parser.add_argument("--per-type", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    lang, n = args.lang, args.per_type

    with SessionLocal.begin() as db:
        old = select(Contribution.id).where(Contribution.lang == lang, Contribution.status == "gold")
        # Los juicios sobre controles previos se descartan; los contadores de acierto se conservan
        db.execute(delete(Review).where(Review.contribution_id.in_(old)))
        db.execute(delete(GoldItem).where(GoldItem.contribution_id.in_(old)))
        db.execute(delete(Contribution).where(Contribution.id.in_(old)))

        entries = db.scalars(select(Entry).where(Entry.lang == lang, is_current(Entry))).all()
        rng.shuffle(entries)

        # Transcripción
        made = 0
        for e in entries:
            if made >= n:
                break
            tokens = db.scalars(select(Alignment).where(Alignment.entry_id == e.id, Alignment.aligned)).all()
            candidates = [t for t in tokens if corrupt(t.token, rng)]
            if not candidates:
                continue
            t = rng.choice(candidates)
            wrong = corrupt(t.token, rng)
            expected = "reject" if made % 2 == 0 else "accept"
            original, proposed = (t.token, wrong) if expected == "reject" else (wrong, t.token)
            add_gold(db, lang, "transcription_fix", "entry", e.id,
                     {"position": t.position, "original": original, "proposed": proposed}, expected)
            made += 1

        # Traducción
        trs = db.scalars(
            select(Translation).join(Entry).where(Entry.lang == lang, is_current(Translation))
        ).all()
        picked = rng.sample(trs, min(n, len(trs) // 2))
        for i, tr in enumerate(picked):
            other = rng.choice([x for x in trs if x.entry_id != tr.entry_id])
            expected = "reject" if i % 2 == 0 else "accept"
            original, proposed = (tr.text, other.text) if expected == "reject" else (other.text, tr.text)
            add_gold(db, lang, "translation_fix", "translation", tr.id,
                     {"original": original, "proposed": proposed}, expected)

        # Glosa (solo lemas frecuentes, con glosa conocida)
        lexs = db.scalars(
            select(Lexeme).where(Lexeme.lang == lang, is_current(Lexeme), Lexeme.frequency >= 50,
                                 Lexeme.gloss.is_not(None), ~Lexeme.is_function_word)
        ).all()
        for i, lx in enumerate(rng.sample(lexs, min(n, len(lexs) // 2))):
            other = rng.choice([x for x in lexs if x.gloss.lower() != lx.gloss.lower()])
            expected = "reject" if i % 2 == 0 else "accept"
            original, proposed = (lx.gloss, other.gloss) if expected == "reject" else (other.gloss, lx.gloss)
            add_gold(db, lang, "gloss_fix", "lexeme", lx.id,
                     {"lemma": lx.lemma, "original": original, "proposed": proposed}, expected)

        counts = db.execute(
            select(Contribution.type, func.count()).where(Contribution.lang == lang, Contribution.status == "gold")
            .group_by(Contribution.type)
        ).all()
    print(f"[{lang}] controles sembrados: {dict(counts)}")


if __name__ == "__main__":
    main()
