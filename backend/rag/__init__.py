"""RAG generation module — contracts, protocols, and service entry point.

Contract version: rag-v1.1-draft

See ``backend/schemas/rag_contract.py`` for the shared Pydantic models.
"""

from backend.rag.chroma_gateway import ChromaRetrievalGateway  # noqa: F401
from backend.rag.openai_compatible_generation import (  # noqa: F401
    OpenAICompatibleGenerationClient,
)
