import pytest

from codecompass.evaluation.embedding_model_comparison import (
    _validate_index_pair,
    _validate_lexical_invariant,
)


def test_index_pair_allows_only_embedding_identity_to_differ() -> None:
    local = {
        "repository_id": "repo",
        "files": 1,
        "symbols": 2,
        "chunks": 2,
        "vectors": 2,
        "chunk_ids_sha256": "chunks",
        "canonical_embedding_text_sha256": "text",
        "embedding_model": "local",
        "dimensions": 768,
    }
    gemini = {
        **local,
        "embedding_model": "gemini-embedding-001",
        "dimensions": 3072,
    }

    _validate_index_pair(local, gemini)

    with pytest.raises(ValueError, match="chunk_ids_sha256"):
        _validate_index_pair(local, {**gemini, "chunk_ids_sha256": "changed"})


def test_lexical_invariant_rejects_changed_ranking() -> None:
    local = [{"case_id": "case", "method": "lexical", "results": [{"chunk_id": "a"}]}]

    _validate_lexical_invariant(local, local)

    changed = [{"case_id": "case", "method": "lexical", "results": [{"chunk_id": "b"}]}]
    with pytest.raises(ValueError, match="lexical rankings changed"):
        _validate_lexical_invariant(local, changed)
