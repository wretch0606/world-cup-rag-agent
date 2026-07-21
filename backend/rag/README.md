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

## Runtime entry points (rag-v1.1-draft)

- `backend/rag/service.py::RagService` — In-process async entry for B→E generation.  Takes
  `RAGRequest`, calls `RetrievalGateway` (D) and `GenerationClient` (LLM), returns
  `RAGResult`.  Never loads models, databases, or API keys directly.

- `backend/rag/protocols.py` — Protocol definitions for `RetrievalGateway` and
  `GenerationClient`.  Concrete implementations live outside `backend/rag/`.

- `backend/schemas/rag_contract.py` — Shared Pydantic v2 models for the full
  B→E→D→E→B chain.  Contract version `rag-v1.1-draft`.

- `backend/rag/chroma_gateway.py::ChromaRetrievalGateway` — Adapts D's synchronous
  Chroma retrieval functions (`query_top_k`, `query_with_rerank`) to the async
  `RetrievalGateway` protocol.  Uses `asyncio.to_thread()` for sync→async bridging.
  Never loads Chroma/BGE/Reranker at import time.

- `backend/rag/openai_compatible_generation.py::OpenAICompatibleGenerationClient` —
  OpenAI-compatible Chat Completions client (DeepSeek by default).  Implements
  `GenerationClient` protocol.  Calls LLM with `response_format={"type": "json_object"}`,
  validates output against a trusted schema, and reconstructs sources/evidence from
  original data so the model can never fabricate references.  Configured via
  `RAG_LLM_*` env vars.
