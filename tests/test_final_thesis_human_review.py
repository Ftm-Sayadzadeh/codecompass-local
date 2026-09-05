from codecompass.evaluation.final_thesis_human_review import _metrics, _paired_delta


def test_human_review_metrics_and_paired_delta() -> None:
    def row(llm: str, correctness: int) -> dict:
        return {
            "case_id": "case-1",
            "embedding_arm": "same",
            "llm_arm": llm,
            "human_scores": {
                "correctness_0_10": correctness,
                "groundedness_0_10": correctness,
                "persian_readability_0_10": correctness,
                "usefulness_0_10": correctness,
                "hallucination": "none",
            },
        }

    rows = [row("qwen", 6), row("glm", 9)]
    assert _metrics(rows)["correctness_0_10"] == {"n": 2, "mean": 7.5}
    paired = _paired_delta(rows, ("case_id", "embedding_arm"), "llm_arm", "qwen", "glm")
    assert paired["paired_cases"] == 1
    assert paired["treatment_minus_control"]["correctness_0_10"] == {"n": 1, "mean": 3.0}
