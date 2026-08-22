"""Retrieval service facade."""

from codecompass.embeddings import EmbeddingProvider
from codecompass.retrieval.hybrid import HybridRetriever
from codecompass.retrieval.lexical import LexicalRetriever
from codecompass.retrieval.models import RetrievalQuery, RetrievalResult
from codecompass.retrieval.semantic import SemanticRetriever
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import VectorIndex


class RetrievalService:
    """Search indexed code chunks with lexical, semantic, or hybrid retrieval."""

    def __init__(self, store: SQLiteMetadataStore, embedding_provider: EmbeddingProvider, vector_index: VectorIndex) -> None:
        self.lexical = LexicalRetriever(store)
        self.semantic = SemanticRetriever(store, embedding_provider, vector_index)
        self.hybrid = HybridRetriever(self.lexical, self.semantic)

    def search_lexical(self, query: RetrievalQuery) -> RetrievalResult:
        """Run lexical retrieval."""
        return RetrievalResult(query=query, results=self.lexical.search(query))

    def search_semantic(self, query: RetrievalQuery) -> RetrievalResult:
        """Run semantic retrieval."""
        return RetrievalResult(query=query, results=self.semantic.search(query))

    def search_hybrid(self, query: RetrievalQuery) -> RetrievalResult:
        """Run hybrid retrieval."""
        return RetrievalResult(query=query, results=self.hybrid.search(query))
