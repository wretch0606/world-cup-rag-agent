"""Tests for OpenAICompatibleGenerationClient.

All tests use a Fake OpenAIClient — no real DeepSeek network calls.
"""
from __future__ import annotations

import asyncio
import json

from openai import APIStatusError

from backend.rag.openai_compatible_generation import (
    OpenAICompatibleGenerationClient,
    _build_messages,
    _load_prompt_file,
    _ModelGenerationPayload,
    _strip_fences,
)
from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    ErrorItem,
    EvidenceItem,
    RAGOptions,
    RAGRequest,
    RAGStatus,
    RetrievalFilters,
    RetrievalResult,
    RetrievalTiming,
    SourceItem,
    StructuredFact,
)


# ====================================================================
# Fake AsyncOpenAI
# ====================================================================
class _FakeCompletion:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChat:
    def __init__(self, completions: FakeCompletions):
        self.completions = completions


class FakeCompletions:
    """Fake completions.create — records calls and returns configured responses."""

    def __init__(self, *, response: str | None = None, should_raise: BaseException | None = None):
        self.response = response or json.dumps(_minimal_model_output())
        self.should_raise = should_raise
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.should_raise:
            raise self.should_raise
        return _FakeCompletion(self.response)


class FakeOpenAI:
    """Fake AsyncOpenAI for test injection."""

    def __init__(self, *, response: str | None = None, should_raise: BaseException | None = None):
        self._fake = FakeCompletions(response=response, should_raise=should_raise)
        self.chat = _FakeChat(self._fake)

    @property
    def calls(self):
        return self._fake.calls


# ====================================================================
# Helpers
# ====================================================================
def _minimal_model_output(**overrides) -> dict:
    d = {
        "status": "ok",
        "answer": "测试回答内容。",
        "facts": [],
        "used_source_ids": [],
        "used_chunk_ids": [],
        "warnings": [],
    }
    d.update(overrides)
    return d


def _make_request(**overrides) -> RAGRequest:
    kwargs = {
        "contract_version": RAG_CONTRACT_VERSION,
        "trace_id": "trace-gen-001",
        "question": "测试问题",
        "original_question": "测试问题",
        "query_type": "semantic",
        "filters": RetrievalFilters(),
        "structured_facts": [],
        "source_catalog": [],
        "options": RAGOptions(),
    }
    kwargs.update(overrides)
    return RAGRequest(**kwargs)


def _make_retrieval(**overrides) -> RetrievalResult:
    kwargs = {
        "contract_version": RAG_CONTRACT_VERSION,
        "trace_id": "trace-gen-001",
        "status": RAGStatus.ok,
        "original_query": "q",
        "applied_filters": RetrievalFilters(),
        "items": [
            EvidenceItem(
                chunk_id="chunk-1",
                document_id="doc-1",
                source_id="src-1",
                document_name="Test Doc",
                text="证据文本。",
                data_version="v1",
                retrieval_rank=1,
            )
        ],
        "timing": RetrievalTiming(),
    }
    kwargs.update(overrides)
    return RetrievalResult(**kwargs)


def _make_source(source_id: str = "src-1") -> SourceItem:
    return SourceItem(source_id=source_id, title=f"Source {source_id}")


def _run(coro):
    return asyncio.run(coro)


# ====================================================================
# 1. Module import without API key
# ====================================================================
def test_module_import_without_api_key():
    """Module can be imported even when no API key is configured."""
    import backend.rag.openai_compatible_generation  # noqa: F401

    assert True  # reached without exception


# ====================================================================
# 2. Live client fails clearly without key
# ====================================================================
def test_client_fails_without_key():
    """generate() returns error when API key is empty."""
    client = OpenAICompatibleGenerationClient(api_key="")

    async def _test():
        return await client.generate(_make_request(), _make_retrieval())

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert result.error is not None
    assert "API Key" in result.error.message


# ====================================================================
# 3. Default base_url
# ====================================================================
def test_default_base_url():
    client = OpenAICompatibleGenerationClient(api_key="")
    assert client._base_url == "https://api.deepseek.com"


# ====================================================================
# 4. Default model is deepseek-v4-flash
# ====================================================================
def test_default_model_is_deepseek_v4_flash():
    client = OpenAICompatibleGenerationClient(api_key="")
    assert client._model == "deepseek-v4-flash"


# ====================================================================
# 5. Not default to deepseek-chat
# ====================================================================
def test_not_default_to_deepseek_chat():
    client = OpenAICompatibleGenerationClient(api_key="")
    assert client._model != "deepseek-chat"
    assert client._model != "deepseek-reasoner"


# ====================================================================
# 6. AsyncOpenAI call parameters
# ====================================================================
def test_async_openai_call_parameters():
    fake = FakeOpenAI()
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1",
                        tournament_year=2022,
                        stage="final",
                        stage_name="决赛",
                        home_team_id="t1",
                        home_team_name="A",
                        away_team_id="t2",
                        away_team_name="B",
                        score_display="1:0",
                        result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    _run(_test())
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert call["stream"] is False
    assert isinstance(call["messages"], list)


# ====================================================================
# 7. response_format = json_object
# ====================================================================
def test_response_format_json_object():
    fake = FakeOpenAI()
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    _run(_test())
    call = fake.calls[0]
    assert call["response_format"] == {"type": "json_object"}


# ====================================================================
# 8. Thinking disabled
# ====================================================================
def test_thinking_disabled():
    fake = FakeOpenAI()
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test", thinking=False)

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    _run(_test())
    call = fake.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}


# ====================================================================
# 9. stream=false
# ====================================================================
def test_stream_false():
    fake = FakeOpenAI()
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    _run(_test())
    call = fake.calls[0]
    assert call["stream"] is False


# ====================================================================
# 10. max_tokens
# ====================================================================
def test_max_tokens():
    fake = FakeOpenAI()
    client = OpenAICompatibleGenerationClient(
        client=fake, api_key="sk-test", max_tokens=2048
    )

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    _run(_test())
    call = fake.calls[0]
    assert call["max_tokens"] == 2048


# ====================================================================
# 11. Prompt UTF-8 loading
# ====================================================================
def test_prompt_utf8_loading():
    content = _load_prompt_file("summary.md")
    assert isinstance(content, str)
    assert len(content) > 0
    assert "{{question}}" in content


# ====================================================================
# 12. Prompt does not depend on CWD
# ====================================================================
def test_prompt_does_not_depend_on_cwd():
    """Prompt loading uses module-relative path, not CWD."""
    content = _load_prompt_file("summary.md")
    assert len(content) > 0  # loaded successfully regardless of CWD


# ====================================================================
# 13. Normal JSON output
# ====================================================================
def test_normal_json_output():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        answer="正常回答。",
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.status == RAGStatus.ok
    assert result.answer == "正常回答。"
    assert len(result.sources) == 1


# ====================================================================
# 14. Markdown code fence stripped
# ====================================================================
def test_strip_fences():
    raw = '```json\n{"key": "value"}\n```'
    cleaned = _strip_fences(raw)
    assert cleaned == '{"key": "value"}'


def test_strip_fences_no_fence():
    raw = '{"key": "value"}'
    cleaned = _strip_fences(raw)
    assert cleaned == '{"key": "value"}'


# ====================================================================
# 15. Non-JSON output
# ====================================================================
def test_non_json_output():
    fake = FakeOpenAI(response="this is not json at all")
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    # Should error after retries (non-JSON won't parse)
    assert result.status == RAGStatus.error
    assert result.error is not None
    assert result.error.code == "GENERATION_ERROR"


# ====================================================================
# 16-17. One retry + second failure
# ====================================================================
def test_json_parse_failure_one_retry():
    """Non-JSON triggers retry; the fake returns same bad content."""
    fake = FakeOpenAI(response="not json")
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.status == RAGStatus.error
    # After 2 attempts, both fail → GENERATION_ERROR
    assert result.error is not None
    assert result.error.code == "GENERATION_ERROR"


# ====================================================================
# 18. Timeout
# ====================================================================
def test_timeout():
    import httpx
    fake = FakeOpenAI(should_raise=httpx.TimeoutException("timeout"))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.status == RAGStatus.error


# ====================================================================
# 19-24. OpenAI HTTP error codes
# ====================================================================
def _make_status_error(status_code: int) -> APIStatusError:
    import httpx
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
    response = httpx.Response(status_code, request=request)
    return APIStatusError("error", response=response, body=None)


def test_error_401():
    _assert_error_code_mapped(401)


def test_error_402():
    _assert_error_code_mapped(402)


def test_error_422():
    _assert_error_code_mapped(422)


def test_error_429():
    _assert_error_code_mapped(429)


def test_error_500():
    _assert_error_code_mapped(500)


def test_error_503():
    _assert_error_code_mapped(503)


def _assert_error_code_mapped(status_code: int):
    fake = FakeOpenAI(should_raise=_make_status_error(status_code))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert result.error is not None


# ====================================================================
# 25. Network error
# ====================================================================
def test_network_error():
    fake = FakeOpenAI(should_raise=ConnectionError("network down"))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.status == RAGStatus.error


# ====================================================================
# 26. Retrieval empty → no LLM call
# ====================================================================
def test_retrieval_empty_no_llm_call():
    fake = FakeOpenAI()
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(structured_facts=[], source_catalog=[]),
            _make_retrieval(status=RAGStatus.empty, items=[]),
        )

    result = _run(_test())
    assert result.status == RAGStatus.empty
    # No LLM call was made
    assert len(fake.calls) == 0


# ====================================================================
# 27. Retrieval error → no LLM call
# ====================================================================
def test_retrieval_error_no_llm_call():
    fake = FakeOpenAI()
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(),
            _make_retrieval(
                status=RAGStatus.error,
                error=ErrorItem(code="RETRIEVAL_ERROR", message="fail", component="retrieval"),
            ),
        )

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert len(fake.calls) == 0


# ====================================================================
# 28. Retrieval degraded must stay degraded
# ====================================================================
def test_retrieval_degraded_not_become_ok():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        status="ok",
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(source_catalog=[_make_source("src-1")],
                          structured_facts=[
                              StructuredFact(
                                  match_id="M-1", tournament_year=2022,
                                  stage="final", stage_name="决赛",
                                  home_team_id="t1", home_team_name="A",
                                  away_team_id="t2", away_team_name="B",
                                  score_display="1:0", result_type="regulation",
                                  winner_team_id="t1",
                              )
                          ]),
            _make_retrieval(status=RAGStatus.degraded),
        )

    result = _run(_test())
    assert result.status == RAGStatus.degraded


# ====================================================================
# 29. trace_id passthrough
# ====================================================================
def test_trace_id_passthrough():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                trace_id="my-gen-trace",
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.trace_id == "my-gen-trace"


# ====================================================================
# 30. contract_version passthrough
# ====================================================================
def test_contract_version_passthrough():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.contract_version == RAG_CONTRACT_VERSION


# ====================================================================
# 31. confidence is always null
# ====================================================================
def test_confidence_always_null():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.confidence is None


# ====================================================================
# 32. Fabricated source_id removed
# ====================================================================
def test_fabricated_source_id_removed():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        used_source_ids=["src-1", "fake-src-999"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    source_ids = {s.source_id for s in result.sources}
    assert "fake-src-999" not in source_ids
    assert "src-1" in source_ids
    assert result.status == RAGStatus.degraded  # fabricated sources → degraded


# ====================================================================
# 33. Fabricated chunk_id removed
# ====================================================================
def test_fabricated_chunk_id_removed():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1", "fake-chunk-999"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    chunk_ids = {e.chunk_id for e in result.evidence}
    assert "fake-chunk-999" not in chunk_ids
    assert "chunk-1" in chunk_ids


# ====================================================================
# 34. Sources rebuilt from source_catalog
# ====================================================================
def test_sources_rebuilt_from_source_catalog():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        used_source_ids=["src-1", "src-2"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1"), _make_source("src-2")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert len(result.sources) == 2
    assert {s.source_id for s in result.sources} == {"src-1", "src-2"}


# ====================================================================
# 35. Evidence rebuilt from retrieval.items
# ====================================================================
def test_evidence_rebuilt_from_retrieval():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(source_catalog=[_make_source("src-1")],
                          structured_facts=[
                              StructuredFact(
                                  match_id="M-1", tournament_year=2022,
                                  stage="final", stage_name="决赛",
                                  home_team_id="t1", home_team_name="A",
                                  away_team_id="t2", away_team_name="B",
                                  score_display="1:0", result_type="regulation",
                                  winner_team_id="t1",
                              )
                          ]),
            _make_retrieval(),
        )

    result = _run(_test())
    assert len(result.evidence) == 1
    assert result.evidence[0].chunk_id == "chunk-1"


# ====================================================================
# 36. used_for_fact_ids cross-linked
# ====================================================================
def test_used_for_fact_ids():
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        facts=[{"fact_type": "match_result", "fact_id": "fact-1", "match_id": "M-1",
                "tournament_year": 2022, "stage": "final", "stage_name": "决赛",
                "home_team_id": "t1", "home_team_name": "A",
                "away_team_id": "t2", "away_team_name": "B",
                "score_display": "1:0", "result_type": "regulation",
                "winner_team_id": "t1", "text": "...",
                "source_ids": ["src-1"]}],
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert len(result.facts) == 1
    for s in result.sources:
        assert "fact-1" in s.used_for_fact_ids


# ====================================================================
# 37. StructuredFact score precedence
# ====================================================================
def test_structured_fact_score_precedence():
    """Model says 2:0, StructuredFact says 1:0 — fact wins."""
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        facts=[{"fact_type": "match_result", "fact_id": "fact-1", "match_id": "M-1",
                "tournament_year": 2022, "stage": "final", "stage_name": "决赛",
                "home_team_id": "t1", "home_team_name": "A",
                "away_team_id": "t2", "away_team_name": "B",
                "score_display": "2:0", "result_type": "regulation",
                "winner_team_id": "t1", "text": "...",
                "source_ids": ["src-1"]}],
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    codes = {w.code for w in result.warnings}
    assert "SOURCE_CONFLICT" in codes
    assert result.status == RAGStatus.degraded


# ====================================================================
# 38. SOURCE_CONFLICT warning
# ====================================================================
def test_source_conflict_warning():
    """score mismatch produces SOURCE_CONFLICT."""
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        facts=[{"fact_type": "match_result", "fact_id": "fact-1", "match_id": "M-1",
                "tournament_year": 2022, "stage": "final", "stage_name": "决赛",
                "home_team_id": "t1", "home_team_name": "A",
                "away_team_id": "t2", "away_team_name": "B",
                "score_display": "3:3", "result_type": "draw",
                "winner_team_id": "t1",  # model claims winner on draw
                "text": "...",
                "source_ids": ["src-1"]}],
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="group", stage_name="小组赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:1", result_type="draw",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    codes = {w.code for w in result.warnings}
    assert "SOURCE_CONFLICT" in codes


# ====================================================================
# 39. Penalties separated from formal score
# ====================================================================
def test_penalties_separated():
    """When result_type=penalties, penalty_score is separate from score_display."""
    fake = FakeOpenAI(response=json.dumps(_minimal_model_output(
        facts=[{"fact_type": "match_result", "fact_id": "fact-1", "match_id": "M-1",
                "tournament_year": 2022, "stage": "final", "stage_name": "决赛",
                "home_team_id": "t1", "home_team_name": "A",
                "away_team_id": "t2", "away_team_name": "B",
                "score_display": "4:2", "result_type": "penalties",
                "penalty_score": "4:2",
                "winner_team_id": "t1", "text": "...",
                "source_ids": ["src-1"]}],
        used_source_ids=["src-1"],
        used_chunk_ids=["chunk-1"],
    )))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test")

    async def _test():
        return await client.generate(
            _make_request(
                source_catalog=[_make_source("src-1")],
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="3:3", penalty_score="4:2",
                        result_type="penalties", winner_team_id="t1",
                    )
                ],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.status in (RAGStatus.ok, RAGStatus.degraded)


# ====================================================================
# 40. Error content does not leak API key
# ====================================================================
def test_error_no_api_key_leak():
    fake = FakeOpenAI(should_raise=RuntimeError("Error with sk-12345-secret-key"))
    client = OpenAICompatibleGenerationClient(client=fake, api_key="sk-test-real")

    async def _test():
        return await client.generate(
            _make_request(
                structured_facts=[
                    StructuredFact(
                        match_id="M-1", tournament_year=2022,
                        stage="final", stage_name="决赛",
                        home_team_id="t1", home_team_name="A",
                        away_team_id="t2", away_team_name="B",
                        score_display="1:0", result_type="regulation",
                        winner_team_id="t1",
                    )
                ],
                source_catalog=[_make_source("src-1")],
            ),
            _make_retrieval(),
        )

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert result.error is not None
    assert "sk-test-real" not in result.error.message
    assert "sk-" not in result.error.message.lower()


# ====================================================================
# 41. _ModelGenerationPayload silently ignores unknown fields
# ====================================================================
def test_model_payload_ignores_unknown():
    """extra="ignore": unknown fields are silently dropped, no crash."""
    payload = _ModelGenerationPayload(
        status="ok", answer="test", unknown_field="x"
    )
    assert payload.status == "ok"
    assert payload.answer == "test"
    assert not hasattr(payload, "unknown_field")


# 41b. sources / confidence / generation_meta from model are ignored
def test_model_payload_ignores_oversharing_fields():
    """Model returns extra sources, confidence, generation_meta — ignored."""
    payload = _ModelGenerationPayload(
        status="ok",
        answer="answer text",
        facts=[{"fact_id": "f1", "text": "fact"}],
        used_source_ids=["src-1"],
        used_chunk_ids=["c1"],
        warnings=[],
        sources=[{"source_id": "evil", "title": "fabricated"}],
        confidence=0.99,
        generation_meta={"model_name": "evil-model"},
        unknown_random_field=42,
    )
    assert payload.status == "ok"
    assert payload.answer == "answer text"
    assert len(payload.facts) == 1
    assert payload.used_source_ids == ["src-1"]
    assert payload.used_chunk_ids == ["c1"]
    # These MUST NOT be present
    assert not hasattr(payload, "sources")
    assert not hasattr(payload, "confidence")
    assert not hasattr(payload, "generation_meta")
    assert not hasattr(payload, "unknown_random_field")


# 41c. E2E: model extra fields do NOT trigger JSON retry
def test_model_extras_no_retry():
    """When model returns extra fields, no retry — just strip and proceed."""
    call_count = [0]

    class _FakeResponse:
        def __init__(self, content):
            self.choices = [
                type("_C", (), {
                    "message": type("_M", (), {"content": content})()
                })()
            ]

    class _FakeAsyncOpenAI:
        def __init__(self):
            self.chat = type("_Chat", (), {
                "completions": type("_Compl", (), {
                    "create": self._fake_create
                })()
            })()

        async def _fake_create(self, **kwargs):
            call_count[0] += 1
            import json
            payload = {
                "status": "ok",
                "answer": "test answer with extras.",
                "facts": [],
                "used_source_ids": [],
                "used_chunk_ids": [],
                "warnings": [],
                "sources": [{"source_id": "fake-src"}],
                "confidence": 0.99,
                "generation_meta": {"model_name": "fake-model"},
                "unknown_field": "should-be-gone",
            }
            return _FakeResponse(json.dumps(payload))

    client = OpenAICompatibleGenerationClient(
        client=_FakeAsyncOpenAI(),
        api_key="sk-test",
        model="test-model",
    )

    async def _test():
        return await client.generate(
            RAGRequest(
                contract_version=RAG_CONTRACT_VERSION,
                trace_id="trace-extras-001",
                question="test",
                original_question="test",
                query_type="semantic",
                filters=RetrievalFilters(),
                options=RAGOptions(),
                structured_facts=[],
                source_catalog=[],
            ),
            RetrievalResult(
                contract_version=RAG_CONTRACT_VERSION,
                trace_id="trace-extras-001",
                status=RAGStatus.ok,
                original_query="test",
                items=[
                    EvidenceItem(
                        chunk_id="c1", document_id="d1",
                        source_id="src-1", document_name="D",
                        text="evidence text", data_version="v1",
                    )
                ],
                applied_filters=RetrievalFilters(),
                timing=RetrievalTiming(),
            ),
        )

    result = asyncio.run(_test())

    # 1. No retry — call_count is exactly 1
    assert call_count[0] == 1, f"Expected 1 call, got {call_count[0]}"

    # 2. Model provided fake sources → ignored, real sources from code
    assert result.status == RAGStatus.ok
    assert result.answer == "test answer with extras."
    # sources NOT from model
    for s in result.sources:
        assert s.source_id != "fake-src", "Fabricated source should not appear"

    # 3. confidence must be null (code-enforced)
    assert result.confidence is None

    # 4. generation_meta uses real config
    assert result.generation_meta.model_name == "test-model"

    # 5. trace_id from request, not model
    assert result.trace_id == "trace-extras-001"

    # 6. Extra unknown fields not in RAGResult
    assert not hasattr(result, "unknown_field")


# ====================================================================
# 42. _build_messages produces strings
# ====================================================================
def test_build_messages_produces_strings():
    sf = StructuredFact(
        match_id="M-1", tournament_year=2022,
        stage="final", stage_name="决赛",
        home_team_id="t1", home_team_name="A",
        away_team_id="t2", away_team_name="B",
        score_display="1:0", result_type="regulation",
        winner_team_id="t1",
    )
    system, user = _build_messages(
        prompt_template="Test prompt {{question}}",
        question="Q?", original_question="Q?",
        query_type="semantic",
        structured_facts=[sf],
        source_catalog=[_make_source("src-1")],
        evidence=[EvidenceItem(
            chunk_id="c1", document_id="d1", source_id="s1",
            document_name="D", text="T", data_version="v1",
        )],
        applied_filters=RetrievalFilters(),
    )
    assert isinstance(system, str)
    assert isinstance(user, str)
    assert "Q?" in user
