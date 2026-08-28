"""Strict public request and response schemas for the local API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(StrictModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(StrictModel):
    error: ErrorBody


class ProviderOverride(StrictModel):
    provider: Literal["ollama", "openai_compatible"] | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: SecretStr | None = Field(default=None, repr=False)
    timeout_seconds: float | None = Field(default=None, gt=0, le=600)


class EmbeddingProviderOverride(ProviderOverride):
    dimensions: int | None = Field(default=None, gt=0)


class IndexProjectRequest(StrictModel):
    repository_path: str = Field(min_length=1, examples=["/path/to/repository"])
    project_name: str | None = Field(default=None, min_length=1, max_length=200)
    embedding: EmbeddingProviderOverride | None = None


class SearchRequest(StrictModel):
    query: str = Field(min_length=1)
    method: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    limit: int = Field(default=10, ge=1, le=50)
    embedding: EmbeddingProviderOverride | None = None


class AskRequest(StrictModel):
    question: str = Field(min_length=1)
    method: Literal["lexical", "semantic", "hybrid"] = "hybrid"
    embedding: EmbeddingProviderOverride | None = None
    llm: ProviderOverride | None = None


class DocumentationRequest(StrictModel):
    identifier: str | int
    language: Literal["en", "fa"] = "en"
    max_tokens: int | None = Field(default=1200, ge=1, le=8000)
    llm: ProviderOverride | None = None


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"


class ProjectResponse(StrictModel):
    id: int
    name: str
    created_at: str
    updated_at: str
    files: int | None = None
    symbols: int | None = None
    chunks: int | None = None
    vector_complete: bool | None = None


class SourceFileResponse(StrictModel):
    id: int
    relative_path: str
    size_bytes: int
    sha256: str
    status: str


class SourceContentResponse(StrictModel):
    id: int
    relative_path: str
    sha256: str
    content: str


class SymbolResponse(StrictModel):
    id: int
    file_id: int
    kind: str
    name: str
    qualified_name: str
    is_async: bool
    start_line: int
    end_line: int
    parameters: list[str]
    returns: str | None


class CitationResponse(StrictModel):
    chunk_id: str
    source_file: str
    symbol_name: str | None
    qualified_name: str | None
    start_line: int
    end_line: int


class RetrievedChunkResponse(CitationResponse):
    score: float
    code: str
    retrieval_method: str


class SearchResponse(StrictModel):
    query: str
    method: str
    results: list[RetrievedChunkResponse]


class AskResponse(StrictModel):
    question: str
    answer: str
    method: str
    citations: list[CitationResponse]
    omitted_context_count: int
    llm_model: str | None
    llm_provider: str | None


class IndexProjectResponse(StrictModel):
    project_id: int
    operation: Literal["indexed", "reindexed"]
    complete: bool
    structural_stats: dict[str, Any]
    vector_stats: dict[str, Any]
    embedding: dict[str, Any]


class DocumentationResponse(StrictModel):
    extracted: dict[str, Any]
    generated: dict[str, Any]
    citations: list[dict[str, Any]]
    generation: dict[str, Any]


class EvaluationResponse(StrictModel):
    scope: Literal["benchmark_evaluation"] = "benchmark_evaluation"
    not_per_answer_confidence: Literal[True] = True
    artifact_sha256: str
    data: dict[str, Any]
