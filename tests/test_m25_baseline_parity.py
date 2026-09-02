from codecompass.evaluation.m25_baseline_parity import run


def test_m25_baseline_parity_reads_frozen_inputs_without_runtime_calls() -> None:
    result = run()
    methods = result["retrieval"]["methods"]
    assert result["retrieval"]["population"] == 54
    assert methods["lexical"]["hit_counts"]["10"] == 13
    assert methods["semantic"]["hit_counts"]["10"] == 8
    assert methods["hybrid"]["hit_counts"]["10"] == 14
    assert all(result["retrieval"]["historical_top10_parity"].values())
    assert result["validation"] == {"provider_calls": 0, "indexing_calls": 0, "source_mutated": False}
