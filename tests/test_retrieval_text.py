from codecompass.retrieval.text import identifier_terms, normalize_retrieval_text


def test_normalization_handles_persian_variants_and_spacing() -> None:
    assert normalize_retrieval_text("ي ك\u200c  Test") == "ی ک test"


def test_identifier_terms_preserve_original_and_split_components() -> None:
    assert identifier_terms("OpenAICompatibleLLMProvider") == (
        "openaicompatiblellmprovider",
        "open",
        "ai",
        "compatible",
        "llm",
        "provider",
    )
    assert identifier_terms("vector_generation_matches") == (
        "vector_generation_matches",
        "vector",
        "generation",
        "matches",
    )
