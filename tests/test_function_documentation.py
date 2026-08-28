from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from dataclasses import asdict
from pathlib import Path

import pytest

from codecompass.documentation import (
    DocumentationError,
    FunctionDocumentationService,
    SymbolResolver,
)
from codecompass.indexing import IndexingService
from codecompass.llm import LLMProviderError, LLMRequest, LLMResponse
from codecompass.storage import SQLiteMetadataStore


class FakeLLMProvider:
    def __init__(self, text: str | None = None, error: LLMProviderError | None = None) -> None:
        self.text = text or valid_output()
        self.error = error
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        return LLMResponse(self.text, "fake-model", "fake-provider")


def valid_output(
    *,
    parameters: tuple[str, ...] = ("name",),
    summary: str = "Builds a greeting.",
    details: str = "Returns a greeting for the supplied name.",
) -> str:
    return json.dumps(
        {
            "summary": summary,
            "detailed_description": details,
            "parameters": [
                {"name": name, "description": f"Description for {name}."} for name in parameters
            ],
            "return_value": "A greeting string.",
            "raises": [],
            "side_effects": [],
            "dependencies": [],
            "notes": [],
        },
        ensure_ascii=False,
    )


@pytest.fixture
def indexed_store(tmp_path: Path) -> tuple[SQLiteMetadataStore, int, Path]:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "a.py").write_text(
        '''
def shared(value):
    return value

def greet(name) -> str:
    return f"Hello {name}"

class Worker:
    async def run(self, item) -> bool:
        return bool(item)
'''.lstrip(),
        encoding="utf-8",
    )
    (repository / "b.py").write_text(
        "def shared(value):\n    return value * 2\n",
        encoding="utf-8",
    )
    store = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    result = IndexingService(store).index_repository(repository, project_name="Example")
    assert result.succeeded and result.project_id is not None
    return store, result.project_id, repository


def test_resolves_by_chunk_id_symbol_id_and_qualified_name(indexed_store) -> None:
    store, project_id, _ = indexed_store
    resolver = SymbolResolver(store)
    greet = next(chunk for chunk in store.list_chunks(project_id) if chunk.qualified_name == "greet")

    by_chunk = resolver.resolve(project_id, greet.chunk_id)
    by_symbol = resolver.resolve(project_id, greet.symbol_id)
    by_name = resolver.resolve(project_id, "greet")

    assert by_chunk.status == by_symbol.status == by_name.status == "resolved"
    assert by_chunk.target == by_symbol.target == by_name.target
    assert by_chunk.target is not None
    assert by_chunk.target.signature == "def greet(name) -> str"


def test_unambiguous_short_name_resolves_method(indexed_store) -> None:
    store, project_id, _ = indexed_store

    result = SymbolResolver(store).resolve(project_id, "run")

    assert result.status == "resolved"
    assert result.target is not None
    assert result.target.citation.qualified_name == "Worker.run"
    assert result.target.signature == "async def run(self, item) -> bool"


def test_ambiguous_name_returns_all_candidates_in_deterministic_order(indexed_store) -> None:
    store, project_id, _ = indexed_store

    result = SymbolResolver(store).resolve(project_id, "shared")

    assert result.status == "ambiguous"
    assert result.target is None
    assert [candidate.relative_source_path for candidate in result.candidates] == ["a.py", "b.py"]


def test_missing_symbol_and_project_are_not_found(indexed_store) -> None:
    store, project_id, _ = indexed_store
    resolver = SymbolResolver(store)

    assert resolver.resolve(project_id, "missing").status == "not_found"
    assert resolver.resolve(999_999, "greet").status == "not_found"


def test_generation_returns_trusted_facts_and_citation(indexed_store) -> None:
    store, project_id, repository = indexed_store
    llm = FakeLLMProvider()

    result = FunctionDocumentationService(store, llm).document_symbol(project_id, "greet")

    citation = result.extracted.citation
    assert result.extracted.signature == "def greet(name) -> str"
    assert result.extracted.parameters == ("name",)
    assert result.extracted.return_annotation == "str"
    assert result.generated.parameters[0].name == "name"
    assert citation == result.citations[0]
    assert citation.relative_source_path == "a.py"
    assert citation.start_line == 4
    assert citation.end_line == 5
    assert citation.chunk_id
    assert citation.content_hash
    source_bytes = (repository / "a.py").read_bytes()
    assert result.extracted.source_file_hash == sha256(source_bytes).hexdigest()
    greet_code = "def greet(name) -> str:\n    return f\"Hello {name}\"\n"
    assert citation.content_hash == sha256(greet_code.encode("utf-8")).hexdigest()
    assert result.generation.provider == "fake-provider"
    assert result.generation.model == "fake-model"
    assert llm.requests[0].temperature == 0.0
    assert "Citations" not in llm.requests[0].prompt


def test_generation_parses_return_errors_effects_dependencies_and_notes(indexed_store) -> None:
    store, project_id, _ = indexed_store
    payload = json.loads(valid_output())
    payload.update(
        {
            "return_value": None,
            "raises": ["ValueError when the source value is invalid."],
            "side_effects": ["Writes to the supplied stream."],
            "dependencies": ["Uses normalize_name."],
            "notes": ["The operation is synchronous."],
        }
    )

    result = FunctionDocumentationService(store, FakeLLMProvider(json.dumps(payload))).document_symbol(
        project_id, "greet"
    )

    assert result.generated.return_value is None
    assert result.generated.raises == ("ValueError when the source value is invalid.",)
    assert result.generated.side_effects == ("Writes to the supplied stream.",)
    assert result.generated.dependencies == ("Uses normalize_name.",)
    assert result.generated.notes == ("The operation is synchronous.",)


def test_generation_supports_persian_without_changing_trusted_metadata(indexed_store) -> None:
    store, project_id, _ = indexed_store
    llm = FakeLLMProvider(
        valid_output(summary="یک پیام خوشامد می‌سازد.", details="نام را در پیام قرار می‌دهد.")
    )

    result = FunctionDocumentationService(store, llm).document_symbol(
        project_id, "greet", language="fa"
    )

    assert result.generated.summary == "یک پیام خوشامد می‌سازد."
    assert result.generation.language == "fa"
    assert result.extracted.citation.relative_source_path == "a.py"
    assert "Write the documentation in Persian." in llm.requests[0].prompt


def test_ambiguity_is_exposed_by_documentation_service(indexed_store) -> None:
    store, project_id, _ = indexed_store

    with pytest.raises(DocumentationError) as raised:
        FunctionDocumentationService(store, FakeLLMProvider()).document_symbol(project_id, "shared")

    assert raised.value.code == "ambiguous"
    assert [candidate.relative_source_path for candidate in raised.value.candidates] == ["a.py", "b.py"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not json", "not valid JSON"),
        ("```json\nnot json\n```", "not valid JSON"),
        ("```json\n{}", "invalid Markdown fence"),
        ("", "empty"),
        (json.dumps({"summary": "only"}), "fields do not match"),
        (valid_output(parameters=("invented",)), "parameters do not match"),
    ],
)
def test_rejects_malformed_or_untrusted_output(indexed_store, text: str, message: str) -> None:
    store, project_id, _ = indexed_store
    llm = FakeLLMProvider(text="placeholder")
    llm.text = text

    with pytest.raises(DocumentationError) as raised:
        FunctionDocumentationService(store, llm).document_symbol(project_id, "greet")

    assert raised.value.code == "invalid_output"
    assert message in raised.value.message


def test_accepts_one_valid_json_markdown_fence(indexed_store) -> None:
    store, project_id, _ = indexed_store
    llm = FakeLLMProvider(f"```json\n{valid_output()}\n```")

    result = FunctionDocumentationService(store, llm).document_symbol(project_id, "greet")

    assert result.generated.summary == "Builds a greeting."


def test_rejects_wrong_types_and_oversized_fields(indexed_store) -> None:
    store, project_id, _ = indexed_store
    wrong_type = json.loads(valid_output())
    wrong_type["raises"] = "ValueError"
    oversized = json.loads(valid_output())
    oversized["summary"] = "x" * 8_001

    for payload in (wrong_type, oversized):
        with pytest.raises(DocumentationError) as raised:
            FunctionDocumentationService(store, FakeLLMProvider(json.dumps(payload))).document_symbol(
                project_id, "greet"
            )
        assert raised.value.code == "invalid_output"


def test_rejects_model_attempts_to_replace_trusted_identity(indexed_store) -> None:
    store, project_id, _ = indexed_store
    payload = json.loads(valid_output())
    payload.update(
        {
            "relative_source_path": "fake.py",
            "start_line": 999,
            "chunk_id": "invented",
            "qualified_name": "Fake.symbol",
        }
    )

    with pytest.raises(DocumentationError) as raised:
        FunctionDocumentationService(store, FakeLLMProvider(json.dumps(payload))).document_symbol(
            project_id, "greet"
        )

    assert raised.value.code == "invalid_output"


@pytest.mark.parametrize(
    ("error_type", "expected_code"),
    [("TimeoutError", "provider_timeout"), ("HTTPError", "provider_failure")],
)
def test_provider_errors_are_mapped_without_secret_leakage(
    indexed_store, error_type: str, expected_code: str
) -> None:
    store, project_id, _ = indexed_store
    secret = "test-secret-value"
    llm = FakeLLMProvider(error=LLMProviderError("fake", "model", error_type, secret))

    with pytest.raises(DocumentationError) as raised:
        FunctionDocumentationService(store, llm).document_symbol(project_id, "greet")

    assert raised.value.code == expected_code
    assert secret not in str(raised.value)
    assert raised.value.__cause__ is None


def test_result_and_prompt_contain_no_absolute_repository_path(indexed_store) -> None:
    store, project_id, repository = indexed_store
    llm = FakeLLMProvider()

    result = FunctionDocumentationService(store, llm).document_symbol(project_id, "greet")
    serialized = json.dumps(asdict(result), ensure_ascii=False)

    assert str(repository) not in serialized
    assert str(repository) not in llm.requests[0].prompt


def test_absolute_indexed_source_path_is_rejected(indexed_store) -> None:
    store, project_id, _ = indexed_store
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE source_files SET relative_path = ? WHERE relative_path = 'a.py'", (r"C:\\private\\a.py",))

    with pytest.raises(DocumentationError) as raised:
        SymbolResolver(store).resolve(project_id, "greet")

    assert raised.value.code == "insufficient_evidence"


def test_posix_absolute_indexed_source_path_is_rejected(indexed_store) -> None:
    store, project_id, _ = indexed_store
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE source_files SET relative_path = ? WHERE relative_path = 'a.py'", ("/private/a.py",))

    with pytest.raises(DocumentationError) as raised:
        SymbolResolver(store).resolve(project_id, "greet")

    assert raised.value.code == "insufficient_evidence"


@pytest.mark.parametrize("identifier", ["", "   ", 0, True, object()])
def test_invalid_identifiers_fail_early(indexed_store, identifier) -> None:
    store, project_id, _ = indexed_store

    with pytest.raises(DocumentationError) as raised:
        SymbolResolver(store).resolve(project_id, identifier)

    assert raised.value.code == "invalid_request"


@pytest.mark.parametrize("max_tokens", [0, -1, True, 1.5])
def test_invalid_max_tokens_fail_before_provider(indexed_store, max_tokens) -> None:
    store, project_id, _ = indexed_store
    llm = FakeLLMProvider()

    with pytest.raises(DocumentationError) as raised:
        FunctionDocumentationService(store, llm).document_symbol(
            project_id, "greet", max_tokens=max_tokens
        )

    assert raised.value.code == "invalid_request"
    assert llm.requests == []
