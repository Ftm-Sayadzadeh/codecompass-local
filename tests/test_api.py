from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codecompass.api import APISettings, create_app
from codecompass.api import app as api_app
from codecompass.api import runtime as api_runtime
from codecompass.embeddings import EmbeddingProviderError, EmbeddingResult
from codecompass.llm import LLMProviderError, LLMResponse
from codecompass.providers import ProviderConfig


class FakeEmbeddingProvider:
    truncate = False

    def __init__(self, error: EmbeddingProviderError | None = None) -> None:
        self.error = error

    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]

    def embed_texts(self, texts) -> tuple[EmbeddingResult, ...]:
        if self.error:
            raise self.error
        return tuple(EmbeddingResult([float(len(text)), 1.0], "fake-embed", 2) for text in texts)


class FakeLLMProvider:
    def __init__(self, error: LLMProviderError | None = None) -> None:
        self.error = error
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        if request.response_format == "json":
            return LLMResponse(
                json.dumps(
                    {
                        "summary": "Returns the supplied value.",
                        "detailed_description": "The function returns its input.",
                        "parameters": [{"name": "value", "description": "Input value."}],
                        "return_value": "The input value.",
                        "raises": [],
                        "side_effects": [],
                        "dependencies": [],
                        "notes": [],
                    }
                ),
                "fake-llm",
                "fake",
            )
        return LLMResponse("Grounded answer.", "fake-llm", "fake")


def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    repo.mkdir()
    (repo / "first.py").write_text("def shared(value: str) -> str:\n    return value\n", encoding="utf-8")
    (repo / "second.py").write_text("def shared(other):\n    return other\n", encoding="utf-8")
    return repo


def artifact(path: Path, *, performance: bool = False) -> None:
    value = {
        "schema_version": "1",
        "generated_at": "2026-01-01T00:00:00Z",
        "complete": True,
        "benchmark": {"questions": 60},
        "configuration": {"methods": ["lexical", "semantic", "hybrid"]},
        "repositories": [{"repository_name": "example", "complete": True}],
        "aggregates": [{"slice": "global", "samples": 180 if performance else 60}],
    }
    if performance:
        value["ranking_consistency"] = {"stable_groups": 180}
        value["measured_runs"] = ["must not be exposed"]
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def api(tmp_path: Path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    performance = tmp_path / "performance.json"
    artifact(baseline)
    artifact(performance, performance=True)
    settings = APISettings(
        database_path=tmp_path / "metadata.sqlite",
        chroma_path=tmp_path / "chroma",
        baseline_artifact=baseline,
        performance_artifact=performance,
        embedding_defaults=ProviderConfig(provider="ollama", embedding_model="fake-embed"),
        llm_defaults=ProviderConfig(provider="ollama", llm_model="fake-llm"),
    )
    llm = FakeLLMProvider()
    monkeypatch.setattr(api_runtime, "create_embedding_provider", lambda config: FakeEmbeddingProvider())
    monkeypatch.setattr(api_app, "create_llm", lambda runtime, override: llm)
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, app.state.runtime, llm, repository(tmp_path)


def index_project(client: TestClient, repo: Path) -> int:
    response = client.post("/projects/index", json={"repository_path": str(repo)})
    assert response.status_code == 200, response.text
    return response.json()["project_id"]


def test_health_project_index_and_navigation(api) -> None:
    client, _, _, repo = api
    assert client.get("/health").json() == {"status": "ok"}

    project_id = index_project(client, repo)
    projects = client.get("/projects").json()
    detail = client.get(f"/projects/{project_id}").json()
    files = client.get(f"/projects/{project_id}/files").json()
    symbols = client.get(f"/projects/{project_id}/symbols", params={"file_id": files[0]["id"]}).json()

    assert projects[0]["id"] == project_id
    assert "root_path" not in str(projects)
    assert detail["vector_complete"] is True
    assert detail["files"] == 2
    assert files[0]["relative_path"] == "first.py"
    assert symbols[0]["qualified_name"] == "shared"


def test_file_content_is_metadata_scoped_and_detects_changes(api) -> None:
    client, _, _, repo = api
    project_id = index_project(client, repo)
    source = client.get(f"/projects/{project_id}/files").json()[0]

    response = client.get(f"/projects/{project_id}/files/{source['id']}/content")
    assert response.status_code == 200
    assert "root_path" not in response.text

    (repo / source["relative_path"]).write_text("def changed():\n    pass\n", encoding="utf-8")
    changed = client.get(f"/projects/{project_id}/files/{source['id']}/content")
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "source_changed"


def test_search_embedding_compatibility_and_legacy_behavior(api) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)

    for method in ("lexical", "semantic", "hybrid"):
        response = client.post(f"/projects/{project_id}/search", json={"query": "shared value", "method": method})
        assert response.status_code == 200, response.text
        assert response.json()["results"]

    mismatch = client.post(
        f"/projects/{project_id}/search",
        json={"query": "shared", "method": "semantic", "embedding": {"model": "other"}},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "embedding_configuration_mismatch"

    collection = runtime.collection(project_id)._ready()
    binding = {key: value for key, value in collection.metadata.items() if not key.startswith("codecompass:embedding_")}
    collection.modify(metadata={**binding, "legacy": 1})
    legacy = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "semantic"})
    lexical = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "lexical"})
    assert legacy.status_code == 409
    assert lexical.status_code == 200


def test_invalid_vector_pointer_fails_closed_with_safe_conflict(api) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)
    vector_index = runtime.collection(project_id)
    vector_index._ready()
    physical_names = {collection.name for collection in vector_index._client.list_collections()}
    vector_index.active_pointer.unlink()

    semantic = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "semantic"})
    lexical = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "lexical"})
    detail = client.get(f"/projects/{project_id}")
    reindex = client.post("/projects/index", json={"repository_path": str(repo)})

    assert semantic.status_code == 409
    assert semantic.json()["error"]["code"] == "vector_index_state_invalid"
    assert lexical.status_code == 200
    assert detail.status_code == 409
    assert detail.json()["error"]["code"] == "vector_index_state_invalid"
    assert reindex.status_code == 409
    assert reindex.json()["error"]["code"] == "vector_index_state_invalid"
    assert {collection.name for collection in vector_index._client.list_collections()} == physical_names


def test_ask_and_documentation_preserve_trusted_citations(api) -> None:
    client, _, llm, repo = api
    project_id = index_project(client, repo)

    answer = client.post(f"/projects/{project_id}/ask", json={"question": "What does shared return?", "method": "lexical"})
    documented = client.post(f"/projects/{project_id}/documentation", json={"identifier": "first.py"})
    ambiguous = client.post(f"/projects/{project_id}/documentation", json={"identifier": "shared"})
    missing = client.post(f"/projects/{project_id}/documentation", json={"identifier": "missing"})

    assert answer.status_code == 200
    assert answer.json()["citations"][0]["source_file"] == "first.py"
    assert documented.status_code == 404
    assert ambiguous.status_code == 409
    assert ambiguous.json()["error"]["details"]["candidates"]
    assert missing.status_code == 404
    assert llm.calls == 1

    symbol_id = client.get(f"/projects/{project_id}/symbols").json()[0]["id"]
    success = client.post(f"/projects/{project_id}/documentation", json={"identifier": symbol_id})
    assert success.status_code == 200, success.text
    assert success.json()["extracted"]["citation"]["relative_source_path"] == "first.py"


def test_provider_failure_timeout_and_incomplete_index_are_safe(api, monkeypatch) -> None:
    client, _, _, repo = api
    project_id = index_project(client, repo)
    secret = "sk-secret-value"
    monkeypatch.setattr(api_app, "create_llm", lambda runtime, override: FakeLLMProvider(LLMProviderError("fake", "model", "TimeoutError", secret)))
    timeout = client.post(f"/projects/{project_id}/documentation", json={"identifier": 1, "llm": {"api_key": secret}})
    assert timeout.status_code == 504
    assert secret not in timeout.text

    runtime = client.app.state.runtime
    runtime.index_lock.acquire()
    try:
        concurrent = client.post("/projects/index", json={"repository_path": str(repo)})
    finally:
        runtime.index_lock.release()
    assert concurrent.status_code == 409
    assert concurrent.json()["error"]["code"] == "indexing_in_progress"

    monkeypatch.setattr(api_runtime, "create_embedding_provider", lambda config: FakeEmbeddingProvider(EmbeddingProviderError("fake", "fake", "TimeoutError", secret)))
    failed = client.post("/projects/index", json={"repository_path": str(repo)})
    assert failed.status_code == 502
    assert secret not in failed.text


def test_validation_errors_redact_api_key_and_paths(api) -> None:
    client, _, _, _ = api
    secret = "sk-validation-secret"
    private_path = "C:/Users/private/secret-repository"
    response = client.post(
        "/projects/index",
        json={"repository_path": {"bad": private_path}, "embedding": {"api_key": [secret]}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert secret not in response.text
    assert private_path not in response.text


def test_evaluation_projections_exclude_raw_runs_and_handle_malformed(api) -> None:
    client, runtime, _, _ = api
    summary = client.get("/evaluation/summary")
    performance = client.get("/evaluation/performance")

    assert summary.status_code == 200
    assert summary.json()["scope"] == "benchmark_evaluation"
    assert summary.json()["not_per_answer_confidence"] is True
    assert "measured_runs" not in performance.text
    assert "descriptive measurements" in performance.text

    runtime.settings.baseline_artifact.write_text("not json", encoding="utf-8")
    malformed = client.get("/evaluation/summary")
    assert malformed.status_code == 503
    assert malformed.json()["error"]["code"] == "evaluation_unavailable"

    runtime.settings.baseline_artifact.unlink()
    missing = client.get("/evaluation/summary")
    assert missing.status_code == 503
    assert missing.json()["error"]["code"] == "evaluation_unavailable"


def test_swagger_has_only_intended_routes(api) -> None:
    client, _, _, _ = api
    paths = set(client.get("/openapi.json").json()["paths"])
    assert paths == {
        "/health",
        "/projects",
        "/projects/{project_id}",
        "/projects/index",
        "/projects/{project_id}/files",
        "/projects/{project_id}/files/{file_id}/content",
        "/projects/{project_id}/symbols",
        "/projects/{project_id}/search",
        "/projects/{project_id}/ask",
        "/projects/{project_id}/documentation",
        "/evaluation/summary",
        "/evaluation/performance",
    }
