from codecompass.evaluation.whole_repo_rag_preflight import (
    BENCHMARK,
    _cost_envelope,
    _read_json,
    _validate_design,
    _validate_no_question_overlap,
)
from codecompass.evaluation.whole_repo_rag_ablation import _DirectGLMProvider, _bootstrap_delta, _prompt
from codecompass.llm import LLMRequest


def test_ablation_benchmark_contract_and_cost_ceiling() -> None:
    benchmark = _read_json(BENCHMARK)

    _validate_design(benchmark)
    _validate_no_question_overlap(benchmark)
    costs = _cost_envelope(
        benchmark,
        {
            "hospital_system": (21_614, 28_918),
            "cs_bookstore": (16_765, 22_453),
            "codecompass": (204_575, 272_866),
        },
    )

    assert len(benchmark["concepts"]) == 18
    assert sum(len(row["questions"]) for row in benchmark["concepts"]) == 36
    assert costs["main_cost_usd_ceiling_range"][1] < costs["full_cost_usd_ceiling_range"][1] < 1


def test_ablation_prompt_changes_only_question_and_context() -> None:
    context = [{
        "chunk_id": "chunk-1", "file_path": "sample.py", "qualified_symbol": "run",
        "line_start": 1, "line_end": 2, "text": "def run():\n    return 1",
    }]

    system_en, prompt_en = _prompt("What does it do?", context)
    system_fa, prompt_fa = _prompt("چه کاری انجام می‌دهد؟", context)

    assert system_en == system_fa
    assert "File: sample.py" in prompt_en
    assert "def run()" in prompt_fa


def test_ablation_disables_reasoning() -> None:
    provider = _DirectGLMProvider("glm", "https://example.com/v1", "secret")

    payload = provider._payload(LLMRequest(prompt="question", max_tokens=2400))

    assert payload["thinking"] == {"type": "disabled"}


def test_paired_bootstrap_is_deterministic() -> None:
    assert _bootstrap_delta([0.25, 0.5, 0.75]) == {
        "mean_delta": 0.5, "ci95_low": 0.25, "ci95_high": 0.75, "concepts": 3,
    }
