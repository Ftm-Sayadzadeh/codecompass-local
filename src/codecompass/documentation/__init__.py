"""Source-grounded function documentation."""

from codecompass.documentation.models import (
    DOCUMENTATION_SCHEMA_VERSION,
    DocumentationCitation,
    DocumentationError,
    DocumentationGenerationMetadata,
    ExtractedDocumentationFacts,
    FunctionDocumentation,
    GeneratedDocumentation,
    ParameterFact,
    ParameterDocumentation,
    ResolutionCandidate,
    ResolvedSymbol,
    SymbolResolution,
)
from codecompass.documentation.facts import FactExtractionError, SyntaxFacts, extract_syntax_facts
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
    "FactExtractionError",
    "ParameterDocumentation",
    "ParameterFact",
    "ResolutionCandidate",
    "ResolvedSymbol",
    "SymbolResolution",
    "SymbolResolver",
    "SyntaxFacts",
    "extract_syntax_facts",
]
