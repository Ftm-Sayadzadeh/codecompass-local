"""Grounded Q&A orchestration."""

from __future__ import annotations

from typing import Callable

from codecompass.llm import LLMProvider, LLMProviderError, LLMRequest
from codecompass.qa.models import NO_EVIDENCE_ANSWER, QAAnswer, QACitation, QAError, QARequest
from codecompass.qa.prompt import QAPromptBuilder
from codecompass.rag import ContextBlock, ContextBuildError, RAGContext, RAGContextBuilder
from codecompass.retrieval import RetrievalError, RetrievalQuery, RetrievalResult
from codecompass.retrieval.models import RetrievalMethod

SearchFn = Callable[[RetrievalQuery], RetrievalResult]


class GroundedQAService:
    """Answer questions with retrieved context and verified citations."""

    def __init__(
        self,
        retrieval_service: object,
        context_builder: RAGContextBuilder,
        prompt_builder: QAPromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.context_builder = context_builder
        self.prompt_builder = prompt_builder
        self.llm_provider = llm_provider

    def answer(self, request: QARequest) -> QAAnswer:
        """Return a grounded answer with metadata-derived citations."""
        self._validate(request)
        retrieval_result = self._retrieve(request)
        context = self._context(retrieval_result, request.max_context_chars)
        citations = self._citations(context)
        if not context.blocks:
            return QAAnswer(
                question=request.question,
                answer=NO_EVIDENCE_ANSWER,
                citations=(),
                retrieval_method=request.retrieval_method,
                omitted_context_count=context.omitted_count,
                llm_model=None,
                llm_provider=None,
            )

        system_prompt, prompt = self.prompt_builder.build(request.question, context)
        try:
            response = self.llm_provider.generate(
                LLMRequest(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
            )
        except LLMProviderError as error:
            raise QAError("llm", error.message) from error

        return QAAnswer(
            question=request.question,
            answer=response.text,
            citations=citations,
            retrieval_method=request.retrieval_method,
            omitted_context_count=context.omitted_count,
            llm_model=response.model,
            llm_provider=response.provider,
        )

    def _validate(self, request: QARequest) -> None:
        if not isinstance(request.question, str) or not request.question.strip():
            raise QAError("request", "Question must be a non-empty string")
        if isinstance(request.project_id, bool) or not isinstance(request.project_id, int) or request.project_id < 1:
            raise QAError("request", "project_id must be a positive integer")
        if request.retrieval_method not in ("lexical", "semantic", "hybrid"):
            raise QAError("request", "Unsupported retrieval method")
        if isinstance(request.retrieval_limit, bool) or not isinstance(request.retrieval_limit, int) or request.retrieval_limit < 1:
            raise QAError("request", "retrieval_limit must be a positive integer")
        if isinstance(request.max_context_chars, bool) or not isinstance(request.max_context_chars, int) or request.max_context_chars < 1:
            raise QAError("request", "max_context_chars must be a positive integer")

    def _retrieve(self, request: QARequest) -> RetrievalResult:
        try:
            return self._search(request.retrieval_method)(
                RetrievalQuery(request.question, request.project_id, request.retrieval_limit)
            )
        except RetrievalError as error:
            raise QAError("retrieval", error.message) from error

    def _search(self, method: RetrievalMethod) -> SearchFn:
        search = getattr(self.retrieval_service, f"search_{method}", None)
        if not callable(search):
            raise QAError("request", "Retrieval service does not support requested method")
        return search

    def _context(self, retrieval_result: RetrievalResult, max_chars: int) -> RAGContext:
        try:
            return self.context_builder.build(retrieval_result, max_chars)
        except ContextBuildError as error:
            raise QAError("context", str(error)) from error

    def _citations(self, context: RAGContext) -> tuple[QACitation, ...]:
        blocks = tuple(sorted(enumerate(context.blocks), key=lambda item: (item[0], item[1].chunk_id)))
        return tuple(self._citation(block) for _, block in blocks)

    def _citation(self, block: ContextBlock) -> QACitation:
        return QACitation(
            chunk_id=block.chunk_id,
            source_file=block.citation.source_file,
            symbol_name=block.citation.symbol_name,
            qualified_name=block.citation.qualified_name,
            start_line=block.citation.start_line,
            end_line=block.citation.end_line,
        )
