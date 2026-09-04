"""Domain models for source-grounded function documentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DOCUMENTATION_SCHEMA_VERSION = "2"

ResolutionStatus = Literal["resolved", "not_found", "ambiguous"]
DocumentationLanguage = Literal["en", "fa"]
DocumentationErrorCode = Literal[
    "invalid_request",
    "not_found",
    "ambiguous",
    "insufficient_evidence",
    "provider_failure",
    "provider_timeout",
    "output_truncated",
    "invalid_output",
]


@dataclass(frozen=True, slots=True)
class DocumentationCitation:
    """Trusted source identity suitable for later code navigation."""

    project_id: int
    project_name: str
    symbol_id: int
    chunk_id: str
    qualified_name: str
    relative_source_path: str
    start_line: int
    end_line: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class ResolvedSymbol:
    """A function or method resolved entirely from indexed metadata."""

    citation: DocumentationCitation
    symbol_type: str
    name: str
    is_async: bool
    parameters: tuple[str, ...]
    return_annotation: str | None
    signature: str
    source_file_hash: str
    source_code: str


@dataclass(frozen=True, slots=True)
class ResolutionCandidate:
    """Compact identity returned when symbol resolution is ambiguous."""

    symbol_id: int
    chunk_id: str
    symbol_type: str
    qualified_name: str
    relative_source_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class SymbolResolution:
    """Deterministic resolution outcome."""

    status: ResolutionStatus
    target: ResolvedSymbol | None = None
    candidates: tuple[ResolutionCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class ParameterFact:
    """A parameter identity and syntax copied directly from the AST."""

    name: str
    annotation: str | None
    default: str | None


@dataclass(frozen=True, slots=True)
class ExtractedDocumentationFacts:
    """Facts copied from parser, chunk, and project metadata."""

    citation: DocumentationCitation
    symbol_type: str
    signature: str
    parameters: tuple[str, ...]
    return_annotation: str | None
    is_async: bool
    source_file_hash: str
    parameter_details: tuple[ParameterFact, ...]
    explicit_raises: tuple[str, ...]
    direct_calls: tuple[str, ...]
    has_explicit_return: bool


@dataclass(frozen=True, slots=True)
class ParameterDocumentation:
    """Generated explanation for one trusted parameter name."""

    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class GeneratedDocumentation:
    """Validated model-generated explanation; it contains no source identity."""

    summary: str
    detailed_description: str
    parameters: tuple[ParameterDocumentation, ...]
    return_value: str | None
    raises: tuple[str, ...]
    side_effects: tuple[str, ...]
    dependencies: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentationGenerationMetadata:
    """Non-secret provenance for one on-demand generation."""

    schema_version: str
    provider: str
    model: str
    language: DocumentationLanguage


@dataclass(frozen=True, slots=True)
class FunctionDocumentation:
    """Structured documentation with trusted facts separated from generated text."""

    extracted: ExtractedDocumentationFacts
    generated: GeneratedDocumentation
    citations: tuple[DocumentationCitation, ...]
    generation: DocumentationGenerationMetadata


class DocumentationError(Exception):
    """A safe domain error suitable for later API mapping."""

    def __init__(
        self,
        code: DocumentationErrorCode,
        message: str,
        *,
        candidates: tuple[ResolutionCandidate, ...] = (),
        provider_error_type: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.candidates = candidates
        self.provider_error_type = provider_error_type
        super().__init__(message)
