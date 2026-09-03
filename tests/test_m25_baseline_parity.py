import hashlib

from codecompass.evaluation.m25_baseline_parity import _matches_line_ending_variant, run


def test_provenance_accepts_only_line_ending_hash_variants() -> None:
    lf = b'{\n  "status": "frozen"\n}\n'
    crlf_hash = hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest()
    reformatted_hash = hashlib.sha256(b'{"status":"frozen"}\n').hexdigest()

    assert _matches_line_ending_variant(lf, crlf_hash)
    assert not _matches_line_ending_variant(lf, reformatted_hash)


def test_m25_baseline_parity_reads_frozen_inputs_without_runtime_calls() -> None:
    result = run()
    methods = result["retrieval"]["methods"]
    assert result["retrieval"]["population"] == 54
    assert methods["lexical"]["hit_counts"]["10"] == 13
    assert methods["semantic"]["hit_counts"]["10"] == 8
    assert methods["hybrid"]["hit_counts"]["10"] == 14
    assert all(result["retrieval"]["historical_top10_parity"].values())
    assert result["validation"] == {"provider_calls": 0, "indexing_calls": 0, "source_mutated": False}
