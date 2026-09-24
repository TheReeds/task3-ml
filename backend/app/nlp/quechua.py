"""Utilidades lingüísticas para quechua sureño (quy).

Provisional: cuando el equipo del modelo entregue su propio segmentador morfológico,
este módulo se reemplaza sin afectar a la API (solo al pipeline de ingesta).
"""

import re

WORD_RE = re.compile(r"[a-zñáéíóúü']+")

# Sufijos nominales, verbales e independientes frecuentes. Se prueban de más largo a
# más corto y se desprenden iterativamente hasta encontrar un lema conocido.
SUFFIXES = sorted(
    set(
        """kuna kunapa kunata kunaman kunapi kunawan kunamanta manta pi pim ta tam man manmi
        wan pa pas qa m mi n y yki nchik ku kunaqa lla llam ña raq taq chu puni ntin yuq sqa
        spa q nki nku rqa rqan rqani ni sun chka nqa nqaku niku nchik chkan chkani ptin ptinqa
        yta ykuy ykuna na nan""".split()
    ),
    key=len,
    reverse=True,
)

MIN_STEM = 3


def normalize(word: str) -> str:
    """Unifica la ortografía de 5 vocales (JW300) con la de 3 vocales (diccionario)."""
    w = word.lower()
    w = w.translate(str.maketrans("áéíóúü", "aiiuuu"))
    return w.replace("e", "i").replace("o", "u")


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _known(stem: str, lemmas) -> str | None:
    """El diccionario registra los verbos en infinitivo (-y): rima- → rimay."""
    if stem in lemmas:
        return stem
    if stem + "y" in lemmas:
        return stem + "y"
    return None


def lemmatize(word: str, lemmas: set[str] | dict, max_steps: int = 4) -> str | None:
    """Devuelve el lema conocido al que se reduce `word` (ya normalizada), o None."""
    if word in lemmas:
        return word
    cur = word
    for _ in range(max_steps):
        for suf in SUFFIXES:
            if cur.endswith(suf) and len(cur) - len(suf) >= MIN_STEM:
                cur = cur[: -len(suf)]
                if found := _known(cur, lemmas):
                    return found
                break
        else:
            return None
    return None


# Palabras funcionales (pronombres, demostrativos, conectores, adverbios gramaticales).
# Se excluyen como palabra secreta de Radar: el objetivo debe ser un término con contenido.
FUNCTION_WORDS = {
    normalize(w)
    for w in """mana manam chay chaymi chayqa kay kaymi hina hinaspa hinaspapas ichaqa ima imayna
    imapas imatapas imanasqa chayna ancha astawan aswan sapa yaqa manaraq ari arí huk pay paykuna
    ñuqa ñuqa ñuqanchik ñuqayku qam qamkuna may maypi pi pipas mayqan hayk'a hayka kunan kaq karqa
    kanqa kachkan kanman nirqa ninku niwan wakin tukuy llapan ña raq hinallataq hinaptinqa chaypi
    chaymanta chaynaqa ichapas icha manachu arí wak wakpi chaykuna kaykuna kani kanki kan karqani
    karqanki kanku kaniku""".split()
}
