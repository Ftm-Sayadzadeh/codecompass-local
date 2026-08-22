from __future__ import annotations

import pytest

from codecompass.rag import ContextBuildError, RAGContextBuilder
from codecompass.retrieval import RetrievedChunk, RetrievalQuery, RetrievalResult


def chunk(
    chunk_id: str,
    score: float,
    source_file: str,
    start_line: int,
    code: str = "print('x')\n",
    qualified_name: str | None = "sample",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        score=score,
        source_file=source_file,
        symbol_name=qualified_name.rsplit(".", 1)[-1] if qualified_name else None,
        qualified_name=qualified_name,
        start_line=start_line,
        end_line=start_line + 2,
        code=code,
        retrieval_method="hybrid",
    )


def result(*chunks: RetrievedChunk) -> RetrievalResult:
    return RetrievalResult(RetrievalQuery("query", 1, 10), chunks)


def test_builds_context_from_retrieval_result() -> None:
    context = RAGContextBuilder().build(result(chunk("a", 1.0, "pkg/a.py", 1)), max_chars=100)

    assert len(context.blocks) == 1
    assert context.blocks[0].chunk_id == "a"
    assert context.total_chars == len("print('x')\n")
    assert context.omitted_count == 0


def test_preserves_citation_metadata_exactly() -> None:
    retrieved = chunk("a", 1.0, "pkg/a.py", 7, "def target():\n    pass\n", "Class.target")

    block = RAGContextBuilder().build(result(retrieved), max_chars=100).blocks[0]

    assert block.citation.source_file == retrieved.source_file
    assert block.citation.symbol_name == retrieved.symbol_name
    assert block.citation.qualified_name == retrieved.qualified_name
    assert block.citation.start_line == retrieved.start_line
    assert block.citation.end_line == retrieved.end_line
    assert block.code == retrieved.code
    assert block.score == retrieved.score
    assert block.retrieval_method == retrieved.retrieval_method


def test_ordering_is_deterministic_with_tie_breakers() -> None:
    context = RAGContextBuilder().build(
        result(
            chunk("d", 0.8, "pkg/b.py", 1),
            chunk("c", 0.8, "pkg/a.py", 2),
            chunk("b", 0.8, "pkg/a.py", 1),
            chunk("a", 0.9, "pkg/z.py", 9),
        ),
        max_chars=1000,
    )

    assert [block.chunk_id for block in context.blocks] == ["a", "b", "c", "d"]


def test_duplicate_chunk_ids_are_removed_deterministically() -> None:
    context = RAGContextBuilder().build(
        result(
            chunk("same", 0.1, "pkg/z.py", 9, "low\n"),
            chunk("same", 0.9, "pkg/a.py", 1, "high\n"),
            chunk("other", 0.8, "pkg/b.py", 1, "other\n"),
        ),
        max_chars=100,
    )

    assert [block.chunk_id for block in context.blocks] == ["same", "other"]
    assert context.blocks[0].code == "high\n"


def test_enforces_character_budget_and_reports_omitted_chunks() -> None:
    context = RAGContextBuilder().build(
        result(
            chunk("a", 1.0, "pkg/a.py", 1, "12345"),
            chunk("b", 0.9, "pkg/b.py", 1, "67890"),
            chunk("c", 0.8, "pkg/c.py", 1, "x"),
        ),
        max_chars=6,
    )

    assert [block.chunk_id for block in context.blocks] == ["a", "c"]
    assert context.total_chars == 6
    assert context.omitted_count == 1


def test_empty_results_build_empty_context() -> None:
    context = RAGContextBuilder().build(result(), max_chars=10)

    assert context.blocks == ()
    assert context.total_chars == 0
    assert context.omitted_count == 0


def test_invalid_budget_raises() -> None:
    with pytest.raises(ContextBuildError):
        RAGContextBuilder().build(result(), max_chars=0)


def test_all_over_budget_chunks_are_omitted() -> None:
    context = RAGContextBuilder().build(
        result(chunk("a", 1.0, "pkg/a.py", 1, "too long")),
        max_chars=3,
    )

    assert context.blocks == ()
    assert context.total_chars == 0
    assert context.omitted_count == 1
