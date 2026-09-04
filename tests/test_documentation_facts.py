from __future__ import annotations

import pytest

from codecompass.documentation import FactExtractionError, extract_syntax_facts


def test_extracts_parameters_defaults_returns_raises_calls_and_async_status() -> None:
    facts = extract_syntax_facts(
        """
async def process(item: str, count: int = 2, *values: float, enabled: bool = True, **options) -> list[str]:
    if not enabled:
        raise ValueError("disabled")
    result = normalize(item)
    await self.persist(result)
    return render(result, count)
""",
        "process",
    )

    assert [(item.name, item.annotation, item.default) for item in facts.parameters] == [
        ("item", "str", None),
        ("count", "int", "2"),
        ("*values", "float", None),
        ("enabled", "bool", "True"),
        ("**options", None, None),
    ]
    assert facts.return_annotation == "list[str]"
    assert facts.is_async is True
    assert facts.explicit_raises == ("ValueError",)
    assert facts.direct_calls == ("ValueError", "normalize", "self.persist", "render")
    assert facts.has_explicit_return is True


def test_nested_definitions_do_not_contaminate_selected_symbol() -> None:
    facts = extract_syntax_facts(
        """
def outer(value):
    def inner():
        hidden()
        raise HiddenError()
        return value
    visible(value)
""",
        "outer",
    )

    assert facts.direct_calls == ("visible",)
    assert facts.explicit_raises == ()
    assert facts.has_explicit_return is False


@pytest.mark.parametrize("source", ["not python", "class Example:\n    pass\n"])
def test_invalid_or_missing_selected_function_fails_safely(source: str) -> None:
    with pytest.raises(FactExtractionError):
        extract_syntax_facts(source, "missing")
