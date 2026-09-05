from codecompass.evaluation.final_thesis_report import _rank_metrics, _stats


def test_final_report_metric_helpers() -> None:
    rows = [{"target_rank": rank} for rank in (1, 3, None, 7)]
    metrics = _rank_metrics(rows)
    assert metrics["hit_at_1"] == 1
    assert metrics["hit_at_3"] == 2
    assert metrics["hit_at_10"] == 3
    assert metrics["mrr_at_10"] == 0.369048
    assert _stats([1.0, 2.0, 3.0, 4.0])["median"] == 2.5
