from codecompass.evaluation.gemini2_embedding_comparison import _decision, _metadata_absolute_paths


def test_decision_distinguishes_strict_gate_from_ranking_preference() -> None:
    key = "global_micro:all:hybrid"
    metrics = {
        "gemini_001": {key: {"top_3": 0.95, "mrr_at_10": 0.83}},
        "gemini_2": {key: {"top_3": 0.95, "mrr_at_10": 0.87}},
    }

    metrics["gemini_001"][key].update(top_1=0.70, evidence_recall_at_10=0.95)
    metrics["gemini_2"][key].update(top_1=0.80, evidence_recall_at_10=0.99)

    decision = _decision(metrics)
    assert decision["strict_superiority_gate_passed"] is False
    assert decision["official_ranking_preference"] == "gemini-embedding-2"


def test_path_scan_ignores_source_text_but_rejects_metadata_paths() -> None:
    assert not _metadata_absolute_paths({"text": r"example C:\\temp\\code.py"})
    assert _metadata_absolute_paths({"repository_path": r"C:\\private\\repo"})
