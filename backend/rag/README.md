# RAG generation assets

This directory contains the initial answer-generation and evaluation prompt assets owned by role E.

## Prompt files

- `exact_match.md`: exact-fact answer-format specification. Under the current draft contract, exact facts are queried and formatted by B without calling the E RAG runtime.
- `relation_query.md`: team relation and advancement questions.
- `penalty_query.md`: formal-score and penalty-shootout separation rules.
- `comparison.md`: cross-tournament comparison rules.
- `summary.md`: fact-and-evidence summary rules.
- `fallback.md`: no-result, out-of-scope, clarification and source-conflict rules.

The runtime ownership and schemas are defined in [`docs/rag-contract-v1-draft.md`](../../docs/rag-contract-v1-draft.md). These Markdown files are initial versioned assets; production loading and model invocation will be implemented after B, D and E freeze the shared Pydantic contract.
