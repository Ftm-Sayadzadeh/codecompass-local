"""Source-grounded function documentation."""

from codecompass.documentation.models import (
    DOCUMENTATION_SCHEMA_VERSION,
    DocumentationCitation,
    DocumentationError,
    DocumentationGenerationMetadata,
    ExtractedDocumentationFacts,
    FunctionDocumentation,
    GeneratedDocumentation,
    ParameterDocumentation,
    ResolutionCandidate,
    ResolvedSymbol,
    SymbolResolution,
)
from codecompass.documentation.service import FunctionDocumentationService, SymbolResolver

__all__ = [
    "DOCUMENTATION_SCHEMA_VERSION",
    "DocumentationCitation",
    "DocumentationError",
    "DocumentationGenerationMetadata",
    "ExtractedDocumentationFacts",
    "FunctionDocumentation",
    "FunctionDocumentationService",
    "GeneratedDocumentation",
    "ParameterDocumentation",
    "ResolutionCandidate",
    "ResolvedSymbol",
    "SymbolResolution",
    "SymbolResolver",
]
