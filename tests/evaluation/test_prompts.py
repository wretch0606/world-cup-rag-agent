"""对六类 Prompt 做离线契约测试，不调用真实大模型。"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = REPO_ROOT / "backend" / "rag" / "prompts"
MOCK_FILE = Path(__file__).resolve().parent / "fixtures" / "prompt_mock_cases.json"

REQUIRED_PROMPT_MARKERS = [
    "{{question}}",
    "{{structured_facts_json}}",
    "{{retrieved_chunks_json}}",
    '"answer"',
    '"facts"',
    '"sources"',
    '"confidence"',
    '"warnings"',
    '"generation_meta"',
]

REQUIRED_OUTPUT_KEYS = {
    "answer",
    "facts",
    "sources",
    "confidence",
    "warnings",
    "generation_meta",
}


def render_prompt(template: str, case: dict) -> str:
    rendered = template.replace("{{question}}", case["question"])
    rendered = rendered.replace(
        "{{structured_facts_json}}",
        json.dumps(case["structured_facts"], ensure_ascii=False),
    )
    rendered = rendered.replace(
        "{{retrieved_chunks_json}}",
        json.dumps(case["retrieved_chunks"], ensure_ascii=False),
    )
    return rendered


def validate_output(case: dict) -> None:
    output = case["expected_output"]
    missing = REQUIRED_OUTPUT_KEYS - output.keys()
    assert not missing, f"{case['category']} 输出缺少字段：{sorted(missing)}"
    assert isinstance(output["answer"], str)
    assert isinstance(output["facts"], list)
    assert isinstance(output["sources"], list)
    assert isinstance(output["warnings"], list)
    assert 0.0 <= float(output["confidence"]) <= 1.0

    for source in output["sources"]:
        for key in ("source_id", "title", "url", "page"):
            assert key in source, f"{case['category']} 来源缺少 {key}"

    if case["category"] == "penalty_query":
        fact = output["facts"][0]
        assert fact["result_type"] == "penalties"
        assert fact["score_display"] == "3:3"
        assert fact["penalty_score"] == "4:2"
        assert "加时赛后" in output["answer"]
        assert "点球大战" in output["answer"]

    if case["category"] == "fallback":
        assert output["facts"] == []
        assert output["warnings"]


def main() -> None:
    cases = json.loads(MOCK_FILE.read_text(encoding="utf-8"))
    assert len(cases) == 6, "模拟用例必须覆盖六类 Prompt"

    seen = set()
    for case in cases:
        prompt_path = PROMPT_DIR / case["prompt_file"]
        assert prompt_path.exists(), f"缺少 Prompt：{prompt_path.name}"
        template = prompt_path.read_text(encoding="utf-8")

        for marker in REQUIRED_PROMPT_MARKERS:
            assert marker in template, f"{prompt_path.name} 缺少标记：{marker}"

        rendered = render_prompt(template, case)
        for placeholder in (
            "{{question}}",
            "{{structured_facts_json}}",
            "{{retrieved_chunks_json}}",
        ):
            assert placeholder not in rendered, (
                f"{prompt_path.name} 渲染后仍有未替换变量：{placeholder}"
            )
        assert case["question"] in rendered
        validate_output(case)
        seen.add(case["category"])
        print(f"PASS {case['category']}: {prompt_path.name}")

    assert seen == {
        "exact_match",
        "relation_query",
        "penalty_query",
        "comparison",
        "summary",
        "fallback",
    }
    print("PASS all: 6/6 prompt contract tests")


if __name__ == "__main__":
    main()
