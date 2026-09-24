import numpy as np

from app.adapters.mock import MockAdapter
from app.nlp.quechua import lemmatize, normalize
from pipeline.build_corpus import alignable_form, fill_unaligned
from pipeline.ingest import percentile_ranks


def test_normalize_unifies_five_vowel_orthography():
    assert normalize("Horqo") == "hurqu"
    assert normalize("cheqap") == "chiqap"


def test_lemmatize_strips_suffix_chain():
    lemmas = {"wasi", "runa"}
    assert lemmatize("wasikunamanta", lemmas) == "wasi"
    assert lemmatize("wasipim", lemmas) == "wasi"
    assert lemmatize("runa", lemmas) == "runa"
    assert lemmatize("mikuy", lemmas) is None


def test_lemmatize_keeps_minimum_stem():
    # "pim" no debe desprenderse dejando una raíz de menos de 3 letras
    assert lemmatize("pim", {"pi"}) is None


def test_alignable_form_drops_digits_and_punctuation():
    charset = set("abcdefghijklmnopqrstuvwxyz'")
    assert alignable_form("Ñawinta,", charset) == "nawinta"
    assert alignable_form("5,539", charset) == ""


def test_fill_unaligned_inherits_gap_and_stays_monotonic():
    out = fill_unaligned(["a", "5,539", "b", "!"], [(0, 100), None, (300, 400), None], 500)
    assert [(t.start_ms, t.end_ms, t.aligned) for t in out] == [
        (0, 100, True), (100, 300, False), (300, 400, True), (400, 500, False),
    ]


def test_fill_unaligned_leading_token():
    out = fill_unaligned(["1990", "wata"], [None, (200, 500)], 600)
    assert (out[0].start_ms, out[0].end_ms) == (0, 200)


def test_percentile_ranks_spans_unit_interval():
    assert percentile_ranks([30, 10, 20]) == [1.0, 0.0, 0.5]


def test_mock_adapter_is_deterministic_and_normalized():
    a = MockAdapter()
    v1, v2 = a.embed(["wasi", "yaku"], "quy"), a.embed(["wasi"], "quy")
    assert v1.shape == (2, a.dim)
    np.testing.assert_allclose(np.linalg.norm(v1, axis=1), 1, rtol=1e-5)
    np.testing.assert_allclose(v1[0], v2[0])
    assert a.translate_inverse(["wasi"], "quy") == ["[spa] wasi"]
