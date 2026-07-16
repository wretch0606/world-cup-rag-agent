# RAG evaluation

Initial evaluation assets for role E:

- `testset.jsonl`: 30 labeled cases, with five cases for each of six categories.
- `fixtures/prompt_mock_cases.json`: offline mock inputs and expected output shapes.
- `test_prompts.py`: validates prompt variables, output fields and critical penalty/fallback rules without calling an LLM.
- `validate_testset.py`: validates JSONL structure, unique IDs and category counts.

Run from the repository root:

```bash
python tests/evaluation/test_prompts.py
python tests/evaluation/validate_testset.py
```

The five `exact_match` cases evaluate the overall B-to-frontend exact-fact path. Under the current contract they are not E runtime generation cases.

Before using the test set for formal results, C must verify the match facts, IDs and source IDs. After the API is available, E still needs to add an online evaluation runner that calls the real endpoint and writes run results.
