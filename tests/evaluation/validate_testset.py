"""校验 testset.jsonl 的结构、数量和六类覆盖情况。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


TESTSET = Path(__file__).resolve().with_name("testset.jsonl")
EXPECTED_TYPES = {
    "exact_match",
    "relation_query",
    "penalty_query",
    "comparison",
    "summary",
    "fallback",
}
REQUIRED_FIELDS = {
    "id",
    "type",
    "question",
    "filters",
    "expected_intent",
    "gold_facts",
    "required_source_ids",
    "must_mention",
    "must_not_contain",
    "expected_warning",
    "notes",
}


def main() -> None:
    cases = []
    for line_number, raw_line in enumerate(
        TESTSET.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            case = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"第 {line_number} 行不是合法 JSON：{exc}") from exc

        missing = REQUIRED_FIELDS - case.keys()
        assert not missing, f"{case.get('id', line_number)} 缺少字段：{sorted(missing)}"
        assert case["type"] in EXPECTED_TYPES, f"未知类型：{case['type']}"
        assert isinstance(case["question"], str) and case["question"].strip()
        assert isinstance(case["gold_facts"], list)
        assert isinstance(case["required_source_ids"], list)
        assert isinstance(case["must_mention"], list)
        assert isinstance(case["must_not_contain"], list)

        if case["type"] == "penalty_query":
            assert case["gold_facts"], f"{case['id']} 缺少点球标准事实"
            fact = case["gold_facts"][0]
            assert fact.get("result_type") == "penalties"
            assert fact.get("score_display") is not None
            assert fact.get("penalty_score") is not None

        if case["type"] == "fallback":
            assert case["expected_warning"] in {
                "NO_RESULT",
                "OUT_OF_SCOPE",
                "NEED_CLARIFICATION",
                "SOURCE_CONFLICT",
                "LOW_CONFIDENCE",
            }

        cases.append(case)

    assert len(cases) == 30, f"题目总数应为30，当前为{len(cases)}"
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)), "存在重复题目 ID"

    counts = Counter(case["type"] for case in cases)
    assert set(counts) == EXPECTED_TYPES
    for category in sorted(EXPECTED_TYPES):
        assert counts[category] == 5, f"{category} 应有5题，当前为{counts[category]}"
        print(f"PASS {category}: {counts[category]} cases")

    print("PASS all: 30 cases, 6 categories, 5 cases each")


if __name__ == "__main__":
    main()
