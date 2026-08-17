# University Proposal — Text-Friendly Summary

> Source: `proposal.pdf`. This file is a working summary for engineering use. The original PDF remains the authoritative university document.

## Project title

**Persian:** سامانه‌ی پرسش‌محور مبتنی بر RAG برای توضیح کدهای پایتون  
**English:** A Question-Driven RAG-Based System for Explaining Python Code

## Problem statement

Many software projects, especially those that have evolved over time or lack sufficient documentation, become difficult for developers to understand. Finding where a specific behavior is implemented, understanding relations between code sections, and identifying the role of program components may consume significant developer time. This affects onboarding, maintenance, debugging, and feature development.

Traditional code search generally relies on text/keywords. If a developer's wording differs from identifier names in the repository, simple textual search may fail. A user might ask where a user token is created while the code uses a different technical identifier. The proposal therefore motivates semantic code search based on natural-language intent.

## Main goal

Design and implement a question-driven RAG system for explaining Python code.

The initial scope is small and medium Python projects. A user asks a natural-language question about project logic. The system attempts to find likely relevant code sections and generate a targeted explanation or initial documentation for those sections.

The goal is **not** fully automatic documentation of an entire codebase. It is targeted explanation/documentation driven by the user's question.

## Expected example behavior

For a question such as:

> «کجا توکن کاربر بعد از ورود ساخته می‌شود؟»

The expected system behavior is:

1. Retrieve related code sections such as login and token-generation functions.
2. Explain the role of each relevant section.
3. Produce initial targeted documentation containing items such as purpose, inputs, outputs, and related files/functions.

## Persian questions

The proposal explicitly considers natural-language questions, including Persian questions, in the experimental scope.

Examples include:

- «کجا احراز هویت کاربر انجام می‌شود؟»
- «کدام بخش مسئول تولید توکن است؟»

The system should use the real repository content to identify relevant code and produce a usable explanation/document.

Where possible, the output should show references to related locations in the code so the user can verify correctness.

## Local processing

Reducing dependence on cloud services and using local/controlled processing is a design consideration. However, completely local execution is **not a mandatory commitment in the official proposal**; it is to be considered depending on hardware and execution constraints.

The approved engineering plan targets local-first processing as an enhancement, but failure to run every component locally would not invalidate the original proposal requirement.

## Proposed method

The project is iterative.

### Related-work study

Study relevant work in areas such as:

- Semantic code search.
- Automatic code documentation/summarization.
- Codebase question answering.
- Language models for code analysis.

### Code analysis

For small/medium Python repositories, inspect project files and use code-structure analysis to identify important units such as:

- Classes.
- Functions.
- Methods.

These units become processable units for retrieval and explanation.

### Semantic retrieval

Create appropriate representations for extracted code sections and store them in a searchable structure. On a user question, retrieve relevant sections.

RAG is used so generated output is grounded more strongly in actual repository content.

### Targeted explanation/documentation

Use retrieved code sections to generate an explanation or initial document tailored to the user's question. The intention is to reduce irrelevant/speculative output.

### User interface

Provide a simple interface where a user can:

- Introduce/select a project.
- Ask a question.
- View retrieved relevant sections.
- Review generated explanation/documentation.

### Evaluation

Select one or more small/medium Python projects and prepare a small set of Persian questions about their logic.

For each question, manually identify relevant files/functions as reference answers.

Evaluate whether the system retrieves the relevant sections.

Also assess generated explanation/documentation for:

- Consistency with code.
- Understandability.
- Usefulness to developers.

When possible, compare with a simpler baseline such as keyword search.

## Related work named in proposal

- CodeSearchNet — semantic code search benchmark/problem framing.
- CodeBERT — shared representations between natural language and programming languages.
- GraphCodeBERT — structural/data-flow information for code representation.
- ProConSuL — project context for code summarization with LLMs.
- Retrieval-Augmented Generation (Lewis et al.) — retrieval + generation architecture.
- Python documentation.
- Tree-sitter documentation.

## Important scope interpretation

The official project is primarily:

**Question-driven retrieval + explanation/documentation of Python code, with Persian natural-language questions and code-grounded evidence.**

Do not reinterpret the proposal as requiring:

- Training a new model.
- Complete codebase documentation.
- Full static analysis.
- Full call graphs.
- Multi-agent code review.
- Multiple programming languages.
- Cloud product features.
