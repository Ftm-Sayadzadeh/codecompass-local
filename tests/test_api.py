from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codecompass.api import APISettings, create_app
from codecompass.api import app as api_app
from codecompass.api import runtime as api_runtime
from codecompass.embeddings import EmbeddingProviderError, EmbeddingResult, OllamaEmbeddingProvider
from codecompass.llm import LLMProviderError, LLMResponse
from codecompass.providers import ProviderConfig
from codecompass.vector_index import ChromaVectorIndex, VectorIndexError


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
    def __init__(
        self,
        error: LLMProviderError | None = None,
        finish_reason: str | None = None,
    ) -> None:
        self.error = error
        self.finish_reason = finish_reason
        self.calls = 0
        self.requests = []

    def generate(self, request):
        self.calls += 1
        self.requests.append(request)
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
                finish_reason=self.finish_reason,
            )
        return LLMResponse(
            "Grounded answer.",
            "fake-llm",
            "fake",
            finish_reason=self.finish_reason,
        )


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


def wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    job: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/projects/index-jobs/{job_id}")
        assert response.status_code == 200, response.text
        job = response.json()
        if job["state"] in {"completed", "failed"}:
            return job
        time.sleep(0.1)
    pytest.fail(f"Indexing job did not finish; last state: {job}")


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


def test_index_job_reports_real_progress_and_resumes_by_id(api) -> None:
    client, runtime, _, repo = api
    progress: list[tuple[str, dict[str, int]]] = []

    result = runtime._index_pipeline(repo, None, None, lambda state, counters: progress.append((state, dict(counters))))
    stages = tuple(dict.fromkeys(state for state, _ in progress))

    assert stages == ("scanning", "parsing", "chunking", "preflight", "embedding", "verifying", "activating")
    for key in {key for _, values in progress for key in values}:
        values = [counters[key] for _, counters in progress if key in counters]
        assert values == sorted(values)
    assert result["complete"] is True

    started = client.post("/projects/index-jobs", json={"project_id": result["project_id"]})
    assert started.status_code == 202, started.text
    assert str(repo) not in started.text
    job = wait_for_job(client, started.json()["id"])
    assert job["state"] == "completed"
    assert job["observed_stages"] == ["scanning"]
    assert job["counters"]["chunks_expected"] == job["counters"]["vectors_stored"]
    assert job["result"]["complete"] is True
    assert job["result"]["strategy"] == "incremental"
    assert job["result"]["no_changes"] is True
    assert job["counters"]["files_parsed"] == 0
    assert client.get("/projects/index-jobs/active").status_code == 204


def test_failed_reindex_preserves_previous_metadata_and_vectors(api, monkeypatch) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)
    old_chunks = tuple(chunk.chunk_id for chunk in runtime.store.list_chunks(project_id))
    old_vectors = runtime.collection(project_id).list_ids(project_id)
    (repo / "first.py").write_text("def changed(value):\n    return value\n", encoding="utf-8")
    monkeypatch.setattr(
        api_runtime,
        "create_embedding_provider",
        lambda config: FakeEmbeddingProvider(EmbeddingProviderError("fake", "fake", "TimeoutError", "private provider detail")),
    )

    started = client.post("/projects/index-jobs", json={"project_id": project_id})
    assert started.status_code == 202
    job = wait_for_job(client, started.json()["id"])

    assert job["state"] == "failed"
    assert job["previous_index_preserved"] is True
    assert job["error"]["stage"] == "embedding"
    assert "private provider detail" not in json.dumps(job)
    assert tuple(chunk.chunk_id for chunk in runtime.store.list_chunks(project_id)) == old_chunks
    assert runtime.collection(project_id).list_ids(project_id) == old_vectors


def test_failed_vector_activation_rolls_back_metadata_and_pointer(api, monkeypatch) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)
    old_chunks = tuple(chunk.chunk_id for chunk in runtime.store.list_chunks(project_id))
    old_index = runtime.collection(project_id)
    old_index._ready()
    old_pointer = old_index.active_pointer.read_text(encoding="utf-8")
    (repo / "first.py").write_text("def changed(value):\n    return value\n", encoding="utf-8")

    def fail_activation(self, replacement) -> None:
        raise VectorIndexError("activation failed")

    monkeypatch.setattr(ChromaVectorIndex, "activate_staged", fail_activation)
    started = client.post("/projects/index-jobs", json={"project_id": project_id})
    job = wait_for_job(client, started.json()["id"])

    assert job["state"] == "failed"
    assert job["previous_index_preserved"] is True
    assert tuple(chunk.chunk_id for chunk in runtime.store.list_chunks(project_id)) == old_chunks
    reopened = runtime.collection(project_id)
    assert reopened.active_pointer.read_text(encoding="utf-8") == old_pointer
    assert reopened.list_ids(project_id) == old_chunks


def test_index_job_validates_target_and_rejects_concurrent_work(api) -> None:
    client, runtime, _, repo = api
    assert client.post("/projects/index-jobs", json={}).status_code == 422
    assert client.post("/projects/index-jobs", json={"repository_path": str(repo), "project_id": 1}).status_code == 422

    runtime.index_lock.acquire()
    try:
        response = client.post("/projects/index-jobs", json={"repository_path": str(repo)})
    finally:
        runtime.index_lock.release()
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "indexing_in_progress"


@pytest.mark.parametrize(
    ("error_type", "code", "status"),
    [
        ("ModelNotFound", "embedding_model_unavailable", 422),
        ("URLError", "embedding_provider_unavailable", 502),
    ],
)
def test_ollama_index_preflight_maps_safe_errors(api, monkeypatch, error_type: str, code: str, status: int) -> None:
    _, runtime, _, _ = api
    provider = OllamaEmbeddingProvider(model="missing")

    def fail() -> None:
        raise EmbeddingProviderError("ollama", "missing", error_type, "private provider response")

    monkeypatch.setattr(provider, "preflight", fail)
    with pytest.raises(api_runtime.APIError) as raised:
        runtime._preflight_embedding(provider)

    assert raised.value.status == status
    assert raised.value.code == code
    assert "private provider response" not in str(raised.value.details)


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
        result = response.json()["results"][0]
        chunk = runtime.store.get_chunk_by_chunk_id(project_id, result["chunk_id"])
        assert result["file_id"] == chunk.file_id
        assert result["symbol_id"] == chunk.symbol_id
        assert result["source_file"] == chunk.relative_path
        assert runtime.store.get_source_file(project_id, result["file_id"]).relative_path == result["source_file"]

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


def test_cross_store_generation_mismatch_fails_vector_reads_closed(api) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)
    with sqlite3.connect(runtime.store.db_path) as connection:
        connection.execute("UPDATE projects SET vector_generation = ? WHERE id = ?", ("0" * 32, project_id))

    semantic = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "semantic"})
    lexical = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "lexical"})
    detail = client.get(f"/projects/{project_id}")

    assert semantic.status_code == 409
    assert semantic.json()["error"]["code"] == "vector_index_state_invalid"
    assert detail.status_code == 200
    assert detail.json()["vector_complete"] is False
    assert lexical.status_code == 200


def test_legacy_null_generation_is_structural_only_until_full_rebuild(api) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)
    with sqlite3.connect(runtime.store.db_path) as connection:
        connection.execute(
            "UPDATE projects SET index_schema_version = NULL, vector_generation = NULL WHERE id = ?",
            (project_id,),
        )

    detail = client.get(f"/projects/{project_id}")
    lexical = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "lexical"})
    semantic = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "semantic"})
    hybrid = client.post(f"/projects/{project_id}/search", json={"query": "shared", "method": "hybrid"})

    assert detail.status_code == 200
    assert detail.json()["vector_complete"] is False
    assert lexical.status_code == 200
    assert semantic.status_code == hybrid.status_code == 409
    assert semantic.json()["error"]["code"] == "vector_index_state_invalid"

    rebuilt = client.post("/projects/index", json={"repository_path": str(repo)})
    assert rebuilt.status_code == 200
    assert rebuilt.json()["strategy"] == "full"
    assert client.get(f"/projects/{project_id}").json()["vector_complete"] is True


@pytest.mark.parametrize("metadata", [{"content_hash": "stale"}, {"project_id": 999}])
def test_project_completeness_sees_every_physical_vector(api, metadata) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)
    runtime.collection(project_id)._ready().upsert(
        ids=["stale-vector"],
        embeddings=[[1.0, 2.0]],
        metadatas=[metadata],
    )

    assert client.get(f"/projects/{project_id}").json()["vector_complete"] is False
    rebuilt = client.post("/projects/index", json={"repository_path": str(repo)})
    assert rebuilt.status_code == 200
    assert rebuilt.json()["strategy"] == "full"
    assert "stale-vector" not in runtime.collection(project_id).list_ids()
    assert client.get(f"/projects/{project_id}").json()["vector_complete"] is True


def test_ask_and_documentation_preserve_trusted_citations(api) -> None:
    client, runtime, llm, repo = api
    project_id = index_project(client, repo)

    answer = client.post(f"/projects/{project_id}/ask", json={"question": "What does shared return?", "method": "lexical"})
    documented = client.post(f"/projects/{project_id}/documentation", json={"identifier": "first.py"})
    ambiguous = client.post(f"/projects/{project_id}/documentation", json={"identifier": "shared"})
    missing = client.post(f"/projects/{project_id}/documentation", json={"identifier": "missing"})

    assert answer.status_code == 200
    answer_citation = answer.json()["citations"][0]
    answer_chunk = runtime.store.get_chunk_by_chunk_id(project_id, answer_citation["chunk_id"])
    assert answer_citation["file_id"] == answer_chunk.file_id
    assert answer_citation["symbol_id"] == answer_chunk.symbol_id
    assert answer_citation["source_file"] == answer_chunk.relative_path == "first.py"
    assert runtime.store.get_source_file(project_id, answer_citation["file_id"]).relative_path == "first.py"
    source = client.get(f"/projects/{project_id}/files/{answer_citation['file_id']}/content")
    assert source.status_code == 200
    assert source.json()["relative_path"] == answer_citation["source_file"]
    assert str(repo) not in answer.text
    assert documented.status_code == 404
    assert ambiguous.status_code == 409
    assert ambiguous.json()["error"]["details"]["candidates"]
    assert missing.status_code == 404
    assert llm.calls == 1

    symbol_id = client.get(f"/projects/{project_id}/symbols").json()[0]["id"]
    success = client.post(f"/projects/{project_id}/documentation", json={"identifier": symbol_id})
    assert success.status_code == 200, success.text
    documentation_citation = success.json()["citations"][0]
    documentation_chunk = runtime.store.get_chunk_by_chunk_id(project_id, documentation_citation["chunk_id"])
    assert documentation_citation["file_id"] == documentation_chunk.file_id
    assert documentation_citation["symbol_id"] == documentation_chunk.symbol_id
    assert documentation_citation["relative_source_path"] == documentation_chunk.relative_path == "first.py"
    assert success.json()["extracted"]["citation"] == documentation_citation
    assert client.get(f"/projects/{project_id}/files/{documentation_citation['file_id']}/content").status_code == 200
    assert str(repo) not in success.text


def test_ask_max_tokens_default_override_validation_and_documentation_independence(api) -> None:
    client, _, llm, repo = api
    project_id = index_project(client, repo)

    default = client.post(f"/projects/{project_id}/ask", json={"question": "What does shared return?", "method": "lexical"})
    explicit = client.post(f"/projects/{project_id}/ask", json={"question": "How does shared work?", "method": "lexical", "max_tokens": 1024})

    assert default.status_code == 200
    assert explicit.status_code == 200
    assert default.json()["finish_reason"] is None
    assert [request.max_tokens for request in llm.requests] == [180, 1024]

    calls = llm.calls
    for invalid in (0, -1, 8001):
        response = client.post(f"/projects/{project_id}/ask", json={"question": "Invalid budget", "method": "lexical", "max_tokens": invalid})
        assert response.status_code == 422
    assert llm.calls == calls

    symbol_id = client.get(f"/projects/{project_id}/symbols").json()[0]["id"]
    documented = client.post(f"/projects/{project_id}/documentation", json={"identifier": symbol_id})
    assert documented.status_code == 200
    assert llm.requests[-1].max_tokens == 1200

    llm.finish_reason = "length"
    truncated = client.post(f"/projects/{project_id}/ask", json={"question": "Explain shared", "method": "lexical"})
    assert truncated.status_code == 200
    assert truncated.json()["finish_reason"] == "length"

    no_evidence = client.post(
        f"/projects/{project_id}/ask",
        json={"question": "definitely_absent_identifier", "method": "lexical"},
    )
    assert no_evidence.status_code == 200
    assert no_evidence.json()["llm_model"] is None
    assert no_evidence.json()["llm_provider"] is None
    assert no_evidence.json()["finish_reason"] is None


def test_provider_cannot_author_documentation_file_id(api, monkeypatch) -> None:
    client, _, _, repo = api
    project_id = index_project(client, repo)

    class ForgedFileIdProvider(FakeLLMProvider):
        def generate(self, request):
            response = super().generate(request)
            value = json.loads(response.text)
            value["file_id"] = 999999
            return LLMResponse(json.dumps(value), response.model, response.provider)

    monkeypatch.setattr(api_app, "create_llm", lambda runtime, override: ForgedFileIdProvider())
    symbol_id = client.get(f"/projects/{project_id}/symbols").json()[0]["id"]
    response = client.post(f"/projects/{project_id}/documentation", json={"identifier": symbol_id})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "documentation_invalid_output"
    assert "999999" not in response.text


def test_missing_trusted_citation_metadata_fails_explicitly(api) -> None:
    client, runtime, _, repo = api
    project_id = index_project(client, repo)

    with pytest.raises(api_runtime.APIError) as raised:
        runtime.citation_chunks(project_id, ("missing-chunk",))

    assert raised.value.status == 500
    assert raised.value.code == "citation_metadata_missing"


def test_provider_failure_timeout_and_incomplete_index_are_safe(api, monkeypatch) -> None:
    client, _, _, repo = api
    project_id = index_project(client, repo)
    secret = "sk-secret-value"
    monkeypatch.setattr(api_app, "create_llm", lambda runtime, override: FakeLLMProvider(LLMProviderError("fake", "model", "TimeoutError", secret)))
    timeout = client.post(f"/projects/{project_id}/documentation", json={"identifier": 1, "llm": {"api_key": secret}})
    assert timeout.status_code == 504
    assert timeout.json()["error"]["details"] == {"provider_error_type": "timeout"}
    assert secret not in timeout.text

    monkeypatch.setattr(
        api_app,
        "create_llm",
        lambda runtime, override: FakeLLMProvider(
            LLMProviderError("fake", "model", "HTTPError", secret)
        ),
    )
    provider_failure = client.post(
        f"/projects/{project_id}/documentation", json={"identifier": 1}
    )
    assert provider_failure.status_code == 502
    assert provider_failure.json()["error"] == {
        "code": "documentation_provider_failure",
        "message": "Documentation provider failed",
        "details": {"provider_error_type": "http_error"},
    }
    assert secret not in provider_failure.text

    monkeypatch.setattr(
        api_app,
        "create_llm",
        lambda runtime, override: FakeLLMProvider(finish_reason="length"),
    )
    truncated = client.post(
        f"/projects/{project_id}/documentation", json={"identifier": 1}
    )
    assert truncated.status_code == 502
    assert truncated.json()["error"] == {
        "code": "documentation_output_truncated",
        "message": "Documentation output was truncated",
        "details": {},
    }

    runtime = client.app.state.runtime
    runtime.index_lock.acquire()
    try:
        concurrent = client.post("/projects/index", json={"repository_path": str(repo)})
    finally:
        runtime.index_lock.release()
    assert concurrent.status_code == 409
    assert concurrent.json()["error"]["code"] == "indexing_in_progress"

    monkeypatch.setattr(api_runtime, "create_embedding_provider", lambda config: FakeEmbeddingProvider(EmbeddingProviderError("fake", "fake", "TimeoutError", secret)))
    (repo / "first.py").write_text("def changed(value):\n    return value\n", encoding="utf-8")
    failed = client.post("/projects/index", json={"repository_path": str(repo)})
    assert failed.status_code == 502
    assert secret not in failed.text


@pytest.mark.parametrize(
    "error_type",
    [
        "invalid_response_encoding",
        "invalid_response_json",
        "invalid_response_top_level",
        "invalid_response_choices",
        "invalid_response_message",
        "invalid_response_content",
        "invalid_response_empty_content",
    ],
)
def test_documentation_api_exposes_safe_invalid_response_subtype(
    api, monkeypatch, error_type: str
) -> None:
    client, _, _, repo = api
    project_id = index_project(client, repo)
    secret = "test-secret-value"
    monkeypatch.setattr(
        api_app,
        "create_llm",
        lambda runtime, override: FakeLLMProvider(
            LLMProviderError("openai_compatible", "model", error_type, secret)
        ),
    )

    response = client.post(
        f"/projects/{project_id}/documentation", json={"identifier": 1}
    )

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "documentation_provider_failure",
        "message": "Documentation provider failed",
        "details": {"provider_error_type": error_type},
    }
    assert secret not in response.text


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
        "/projects/index-jobs",
        "/projects/index-jobs/active",
        "/projects/index-jobs/{job_id}",
        "/projects/{project_id}/files",
        "/projects/{project_id}/files/{file_id}/content",
        "/projects/{project_id}/symbols",
        "/projects/{project_id}/search",
        "/projects/{project_id}/ask",
        "/projects/{project_id}/documentation",
        "/evaluation/summary",
        "/evaluation/performance",
    }
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert "file_id" in schemas["CitationResponse"]["properties"]
    assert "symbol_id" in schemas["CitationResponse"]["properties"]
    assert "file_id" in schemas["RetrievedChunkResponse"]["properties"]
    assert "file_id" in schemas["DocumentationCitationResponse"]["properties"]
    assert "finish_reason" in schemas["AskResponse"]["properties"]
    assert "finish_reason" not in schemas["AskResponse"]["required"]
