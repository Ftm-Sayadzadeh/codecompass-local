# First Prompt for Codex — Planning Only

Copy the text below into Codex after placing this starter pack in the repository root.

---

You are joining this repository as the primary implementation agent for a bachelor's final project.

Before writing any code, carefully read:

- AGENTS.md
- PROJECT_BRIEF.md
- ROADMAP.md
- PLANS.md
- README.md
- docs/PROPOSAL_SUMMARY.md
- docs/RESEARCH_NOTES_SUMMARY.md

The original university proposal and research notes are also stored in `docs/proposal.pdf` and `docs/research-notes.docx` for reference.

Source-of-truth priority is defined in AGENTS.md. The university proposal is the primary authority for required academic scope. The research notes contain optional ideas and must not automatically expand the project.

The project has an approximately 21-day development window. We want a strong and polished MVP+, but correctness, evaluation, reliability, and demo quality matter more than feature count.

YOUR TASK IN THIS TURN IS PLANNING ONLY.

Do not create or modify implementation files yet. Do not install dependencies yet. Do not start coding.

Please do the following:

1. Summarize your understanding of the problem and the final user workflow.
2. Separate clearly:
   - official proposal requirements,
   - approved MVP+ features,
   - should-have features,
   - stretch features.
3. Identify contradictions or ambiguous decisions across the documents.
4. Identify unnecessary complexity and anything you recommend simplifying.
5. Propose the backend architecture and module boundaries.
6. Propose the core data models and ownership of metadata.
7. Propose the repository indexing pipeline.
8. Propose the retrieval architecture for keyword, semantic, and hybrid search.
9. Explain how Persian queries should connect to English Python code without overcomplicating the first version.
10. Propose the RAG context-building and citation architecture, ensuring file/symbol/line citations cannot be hallucinated by the LLM.
11. Propose the function-documentation pipeline.
12. Propose the FastAPI API surface at a high level.
13. Propose the minimum frontend information architecture for a strong demo.
14. Propose the evaluation architecture, dataset schema, Top-1/Top-3/MRR computation, and documentation evaluation.
15. Review the 21-day roadmap and change the order only when there is a clear dependency or risk reason.
16. Define acceptance criteria for every major milestone.
17. Identify the critical path required to satisfy the university proposal.
18. Identify which features should be dropped first if the project falls behind schedule.
19. List the most important technical risks and mitigations.
20. Recommend a minimal initial dependency set, but do not install anything.

Important constraints:

- Python-only MVP.
- Do not add fine-tuning.
- Do not add a full call graph.
- Do not add a second programming language.
- Do not add cloud deployment, auth, multi-user features, GitHub PR integration, or a VS Code extension.
- Do not use implementation speed from AI as a reason to expand scope.
- Prefer explicit, testable code over framework-heavy orchestration.
- Avoid LangChain/LlamaIndex in the initial architecture unless you can demonstrate a specific need that cannot be met cleanly with a small explicit pipeline.
- Retrieval quality must be validated before depending on LLM answer quality.
- Verified citations must come from deterministic metadata, not model-generated file paths or line numbers.

At the end, provide exactly these sections:

A. Project Understanding  
B. Scope Classification  
C. Recommended Architecture  
D. Module Map  
E. Data Model  
F. Milestone Dependency Graph  
G. Reviewed 21-Day Roadmap  
H. Testing and Evaluation Strategy  
I. Risks and Mitigations  
J. Features to Drop First if Behind Schedule  
K. Definition of Done  
L. Open Decisions Requiring My Approval

Wait for my approval before implementation.
