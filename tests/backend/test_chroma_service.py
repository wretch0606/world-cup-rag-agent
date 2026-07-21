"""Tests for Chroma service runtime configuration and offline embeddings."""

from __future__ import annotations

import math

from backend.services.chroma_service import HashEmbeddingFunction, _find_file


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    embedding_function = HashEmbeddingFunction(dimensions=128)

    first = embedding_function(["2022年世界杯决赛"])[0]
    second = embedding_function(["2022年世界杯决赛"])[0]

    assert list(first) == list(second)
    assert len(first) == 128
    assert math.isclose(
        math.sqrt(sum(value * value for value in first)),
        1.0,
        rel_tol=1e-6,
    )


def test_hash_embedding_preserves_lexical_overlap() -> None:
    embedding_function = HashEmbeddingFunction(dimensions=384)
    query, relevant, unrelated = embedding_function(
        [
            "阿根廷法国世界杯决赛",
            "世界杯决赛阿根廷对阵法国",
            "摩洛哥对阵西班牙八分之一决赛",
        ]
    )

    assert _cosine(query, relevant) > _cosine(query, unrelated)


def test_data_pipeline_lookup_paths_are_available() -> None:
    assert _find_file("team_aliases.json") is not None
    assert _find_file("stage_mapping.json") is not None
