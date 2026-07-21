"""Initialize and validate the offline Chroma demo collection."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
DEFAULT_FACTS_PATH = ROOT_DIR / "data" / "generated" / "demo_match_facts.jsonl"
DEFAULT_CHROMA_DIR = ROOT_DIR / "data" / "generated" / "chroma_demo"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Initialize the offline Chroma demo collection.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CHROMA_DIR)
    args = parser.parse_args(argv)

    facts_path = args.facts.resolve()
    chroma_dir = args.output_dir.resolve()
    if not facts_path.is_file():
        raise FileNotFoundError(
            f"Demo facts not found at {facts_path}. Run scripts/init_demo_data.py first."
        )

    chroma_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CHROMA_DATA_DIR"] = str(chroma_dir)
    os.environ["EMBEDDING_MODE"] = "hash"

    from backend.rag.chroma_gateway import ChromaRetrievalGateway
    from backend.schemas.common import StageEnum
    from backend.schemas.rag_contract import (
        RAG_CONTRACT_VERSION,
        RAGOptions,
        RAGStatus,
        RetrievalFilters,
        RetrievalRequest,
    )
    from backend.services.chroma_service import (
        COLLECTION_FACTS,
        RetrievalStatus,
        get_collection_stats,
        import_match_facts,
        query_structured,
        reset_all,
    )

    reset_all()
    imported = import_match_facts(str(facts_path))
    response = query_structured(
        "2022年阿根廷队在世界杯决赛的表现",
        k=3,
        collection=COLLECTION_FACTS,
        use_query_rewrite=True,
        use_rerank=False,
    )
    stats = get_collection_stats()

    facts_stats = stats[COLLECTION_FACTS]
    if imported != 6 or facts_stats["total_chunks"] != 6:
        raise RuntimeError(f"Unexpected Chroma demo size: imported={imported}, stats={facts_stats}")
    if response.status != RetrievalStatus.OK or not response.candidates:
        raise RuntimeError(f"Chroma demo retrieval failed: {response.to_dict()}")

    top = response.candidates[0]
    metadata = top.get("metadata", {})
    if metadata.get("stage") != "final" or "team_ARG" not in metadata.get("team_ids", []):
        raise RuntimeError(f"Unexpected Chroma demo result: {top}")

    gateway_result = asyncio.run(
        ChromaRetrievalGateway().retrieve(
            RetrievalRequest(
                contract_version=RAG_CONTRACT_VERSION,
                trace_id="demo-chroma-smoke",
                query="2022年阿根廷队在世界杯决赛的表现",
                original_question="2022年阿根廷队在世界杯决赛的表现",
                filters=RetrievalFilters(
                    years=[2022],
                    team_ids=["team_ARG"],
                    stages=[StageEnum.final],
                ),
                options=RAGOptions(
                    retrieval_top_k=3,
                    rerank_top_n=3,
                    use_query_rewrite=False,
                    use_reranker=False,
                ),
            )
        )
    )
    if gateway_result.status != RAGStatus.ok or not gateway_result.items:
        raise RuntimeError(f"Chroma gateway validation failed: {gateway_result.model_dump()}")
    if gateway_result.items[0].match_id != metadata.get("match_id"):
        raise RuntimeError(
            f"Chroma gateway returned a different top match: {gateway_result.items[0].match_id}"
        )

    print("\nChroma live-demo data is ready:")
    print(f"  directory: {_display_path(chroma_dir)}")
    print(f"  collection: {COLLECTION_FACTS}")
    print(f"  chunks: {facts_stats['total_chunks']}")
    print(f"  top match: {metadata.get('match_id', '')}")
    print(f"  gateway status: {gateway_result.status.value}")
    print("  embedding: hash (offline demo only)")
    return 0


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
