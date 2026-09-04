from codecompass.evaluation.official_embedding_comparison import _transition


def test_transition_classification() -> None:
    assert _transition(None, 4) == "recovered"
    assert _transition(5, 2) == "improved"
    assert _transition(3, 3) == "stable"
    assert _transition(2, 5) == "regressed"
    assert _transition(2, None) == "lost"
