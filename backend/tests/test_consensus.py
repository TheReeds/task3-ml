from app.config import Settings
from app.services.consensus import Vote, decide, reliability, weighted_score
from app.services.taller import fleiss_kappa

CFG = Settings()


def test_weighted_score_ignores_unsure():
    votes = [Vote("accept", 1.0), Vote("reject", 0.5), Vote("unsure", 1.0)]
    assert weighted_score(votes) == 1.0 / 1.5


def test_no_unilateral_approval_even_with_full_weight():
    assert decide([Vote("accept", 1.0)], CFG) == (None, 1.0)


def test_three_default_reviewers_resolve():
    assert decide([Vote("accept", 0.5)] * 2, CFG)[0] is None  # peso 1.0 < 1.5
    assert decide([Vote("accept", 0.5)] * 3, CFG)[0] == "accepted"
    assert decide([Vote("reject", 0.5)] * 3, CFG)[0] == "rejected"


def test_high_weight_reviewers_resolve_faster():
    assert decide([Vote("accept", 0.8), Vote("accept", 1.0)], CFG)[0] == "accepted"


def test_split_vote_stays_pending_then_rejected_at_cap():
    split = [Vote("accept", 0.5), Vote("reject", 0.5)] * 3
    assert decide(split, CFG)[0] is None
    assert decide(split + [Vote("accept", 0.5)], CFG)[0] == "rejected"


def test_reliability_starts_at_half_and_is_bounded():
    assert reliability(0, 0, False, CFG) == 0.5
    assert reliability(20, 20, False, CFG) == CFG.reliability_cap
    assert reliability(20, 0, False, CFG) == 0.1


def test_only_proven_natives_exceed_cap():
    assert reliability(3, 3, True, CFG) == CFG.reliability_cap  # pocas pruebas
    assert reliability(10, 10, True, CFG) > CFG.reliability_cap
    assert reliability(10, 6, True, CFG) < CFG.reliability_cap  # bajo desempeño


def test_fleiss_kappa():
    assert fleiss_kappa([["accept"] * 3, ["reject"] * 3]) == 1.0
    assert fleiss_kappa([["accept", "reject"], ["accept", "reject"]]) < 0
    assert fleiss_kappa([["accept"]]) is None
