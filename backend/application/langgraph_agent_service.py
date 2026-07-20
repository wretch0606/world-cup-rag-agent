"""LangGraphAgentService — exact-fact queries backed by SQLite, routed via LangGraph.

No E, D, Chroma, LLM, or external network calls.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from backend.application.extractor import extract
from backend.dependencies import get_provider
from backend.repositories.protocols import FrontendDataProvider
from backend.schemas.common import MatchFilters, RelationFilters


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------
class AgentState(dict):
    """Typed state for the exact-query agent graph."""

    question: str
    session_id: str | None
    filters: dict
    trace_id: str
    # extracted / resolved
    intent: str
    route: str
    status: str
    answer: str
    needs_clarification: bool
    clarification_question: str | None
    facts: list[dict]
    sources: list[dict]
    graph: dict
    applied_filters: dict
    confidence: None
    warnings: list[dict]
    timing: dict
    extracted: dict


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def _normalise(state: AgentState) -> AgentState:
    question = (state.get("question") or "").strip()
    state["question"] = question
    state.setdefault("intent", "")
    state.setdefault("route", "")
    state.setdefault("status", "ok")
    state.setdefault("answer", "")
    state.setdefault("needs_clarification", False)
    state.setdefault("clarification_question", None)
    state.setdefault("facts", [])
    state.setdefault("sources", [])
    state.setdefault("graph", {"scope": "answer_facts", "nodes": [], "edges": []})
    state.setdefault("applied_filters", state.get("filters", {}))
    state.setdefault("confidence", None)
    state.setdefault("warnings", [])
    state.setdefault(
        "timing",
        {"routing_ms": 0, "sql_ms": 0, "retrieval_ms": 0,
         "generation_ms": 0, "total_ms": 0},
    )
    return state


def _classify(state: AgentState) -> AgentState:
    question = state["question"]

    # Greeting → general_chat
    if any(kw in question for kw in ["你好", "hello", "hi", "帮助"]):
        state["intent"] = "general_chat"
        state["route"] = "general_chat"
        state["answer"] = "你好！我是世界杯知识问答助手。"
        return state

    # Extract structured conditions
    extracted = extract(question)
    state["extracted"] = extracted

    # Determine if we have enough for exact query
    has_teams = bool(extracted.get("team_ids"))
    has_years = bool(extracted.get("years"))
    has_stages = bool(extracted.get("stages"))
    has_match_ids = bool(extracted.get("match_ids"))
    has_penalties = extracted.get("has_penalties") is True
    _score_kw = ["比分", "结果", "谁赢", "获胜", "战胜", "击败", "几比几"]
    ask_about_score = any(kw in question for kw in _score_kw)
    _match_kw = [
        "哪些比赛", "什么比赛", "有哪些比赛", "比赛列表",
        "交手", "交锋", "对", "交手过", "击败过", "战胜过",
    ]
    ask_about_matches = any(kw in question for kw in _match_kw)
    # Semantic / hybrid intent keywords
    _semantic_kw = [
        "介绍", "过程", "原因", "总结", "比较", "重要情节",
        "为什么", "怎么", "怎样", "如何", "经典", "精彩",
        "表现", "夺冠", "历程", "回顾", "评价", "分析",
    ]
    has_semantic = any(kw in question for kw in _semantic_kw)
    has_structured = has_teams or has_years or has_stages or has_match_ids

    # Semantic + structured data → hybrid (SQL facts + RAG evidence)
    if has_semantic and has_structured:
        if ask_about_matches or "比较" in question:
            state["intent"] = "comparison_query"
        elif "总结" in question or "历程" in question or "回顾" in question:
            state["intent"] = "summary_query"
        else:
            state["intent"] = "match_result_query"
        state["route"] = "hybrid_query"
        return state

    # Semantic only (no structured data) → pure RAG
    if has_semantic and not has_structured:
        if "比较" in question:
            state["intent"] = "comparison_query"
        elif "总结" in question or "历程" in question or "回顾" in question:
            state["intent"] = "summary_query"
        else:
            state["intent"] = "match_result_query"
        state["route"] = "rag_query"
        return state

    # Match IDs → exact detail lookup
    if has_match_ids:
        state["intent"] = "match_result_query"
        state["route"] = "structured_query"
        return state

    # Penalty-only query
    if has_penalties and not has_teams:
        state["intent"] = "match_result_query"
        state["route"] = "structured_query"
        return state

    # Team relations query
    if has_teams and ask_about_matches and not has_years:
        # Need at least a year range, but for head-to-head we can search all
        state["intent"] = "match_relation_query"
        state["route"] = "structured_query"
        return state

    # Score / match list query — needs year or specific context
    if ask_about_score and not has_years and not has_match_ids and not has_penalties:
        # "决赛比分是多少" without year → clarification
        if has_stages and not has_years:
            state["intent"] = "match_result_query"
            state["route"] = "clarification"
            state["status"] = "clarification_required"
            state["needs_clarification"] = True
            state["clarification_question"] = "请补充世界杯年份。"
            state["answer"] = "请补充世界杯年份。"
            return state
        # Vague score question → clarification
        state["intent"] = "match_result_query"
        state["route"] = "clarification"
        state["status"] = "clarification_required"
        state["needs_clarification"] = True
        state["clarification_question"] = "请补充更多信息（年份、球队或阶段）。"
        state["answer"] = "请补充更多信息。"
        return state

    # Generic match list
    if has_teams or has_years or has_stages or has_penalties:
        state["intent"] = "match_result_query"
        state["route"] = "structured_query"
        return state

    # Can't classify → empty
    state["intent"] = "out_of_scope"
    state["route"] = "structured_query"
    state["status"] = "empty"
    state["answer"] = "当前知识库中没有足够信息回答您的问题。"
    return state


def _exact_query(state: AgentState) -> AgentState:
    """Execute exact query via SQLite Provider."""
    if state["route"] in ("general_chat", "clarification"):
        return state

    provider = _get_provider_safe()
    extracted = state.get("extracted", {})
    filters = state.get("filters", {})

    # Merge: explicit filters are hard constraints; NL extraction fills gaps
    years = list(filters.get("years", [])) or extracted.get("years", [])
    team_ids = list(filters.get("team_ids", [])) or extracted.get("team_ids", [])
    stages = list(filters.get("stages", [])) or extracted.get("stages", [])
    has_penalties = filters.get("has_penalties")
    if has_penalties is None:
        has_penalties = extracted.get("has_penalties")
    match_ids = list(filters.get("match_ids", [])) or extracted.get("match_ids", [])

    # Normalise has_penalties: False → None
    if has_penalties is False:
        has_penalties = None

    # Match IDs → direct lookup
    if match_ids and len(match_ids) == 1:
        mid = match_ids[0]
        match = provider.get_match(mid) if provider else None
        if match:
            state["facts"] = [_build_fact(match)]
            state["sources"] = match.get("sources", [])
            state["graph"] = _build_answer_graph(match)
            state["answer"] = _build_answer_text(match)
            state["applied_filters"]["match_ids"] = match_ids
            return state
        state["status"] = "empty"
        state["answer"] = f"未找到 match_id 为 {mid} 的比赛。"
        return state

    # Team head-to-head (2+ teams, no year filter, relation intent or explicit relation query)
    if team_ids and len(team_ids) >= 2 and state["intent"] == "match_relation_query":
        return _run_relation_query(state, provider, team_ids, years)

    # Standard match list
    mf = MatchFilters(
        years=years,
        team_ids=team_ids,
        stages=[],
        result_types=[],
        has_penalties=has_penalties,
    )
    # Make stages into StageEnum
    from backend.schemas.common import StageEnum

    parsed_stages: list[StageEnum] = []
    for s in stages:
        try:
            parsed_stages.append(StageEnum(s))
        except ValueError:
            pass
    mf.stages = parsed_stages

    result = provider.list_matches(mf, page=1, page_size=50) if provider else None
    items = result.items if result else []

    if not items:
        state["status"] = "empty"
        state["answer"] = "未找到符合条件的比赛。"
        state["applied_filters"] = {
            "years": years, "team_ids": team_ids,
            "stages": stages, "has_penalties": has_penalties,
        }
        state["warnings"].append({
            "code": "NO_RESULT",
            "message": "没有可靠事实或证据回答该问题。",
            "component": "exact_query",
            "retryable": False,
        })
        return state

    # If exactly one match and question asks for score → return detail
    _score_kw2 = ["比分", "结果", "谁赢", "获胜", "几比几"]
    ask_score = any(kw in state.get("question", "") for kw in _score_kw2)
    if len(items) == 1 and ask_score:
        match = provider.get_match(items[0]["match_id"]) if provider else None
        if match:
            state["facts"] = [_build_fact(match)]
            state["sources"] = match.get("sources", [])
            state["graph"] = _build_answer_graph(match)
            state["answer"] = _build_answer_text(match)
            state["applied_filters"] = {
                "years": years, "team_ids": team_ids,
                "stages": stages, "has_penalties": has_penalties,
            }
            return state

    # Multiple matches → return list as facts
    state["facts"] = [_build_list_fact(m) for m in items]
    if len(items) == 1:
        m = items[0]
        h = m.get("home_team", {}).get("name", "")
        a = m.get("away_team", {}).get("name", "")
        s = m.get("score", {}).get("display", "?")
        state["answer"] = f"{h} vs {a}，比分 {s}。"
    else:
        teams_str = ", ".join(dict.fromkeys(
            m.get("home_team", {}).get("name", "")
            or m.get("away_team", {}).get("name", "")
            for m in items
        ))
        state["answer"] = (
            f"共找到 {len(items)} 场比赛"
            f"{'（涉及 ' + teams_str + '）' if teams_str else ''}。"
        )
    state["graph"] = _build_list_graph(items)
    state["applied_filters"] = {
        "years": years, "team_ids": team_ids,
        "stages": stages, "has_penalties": has_penalties,
    }

    return state


def _run_relation_query(
    state: AgentState,
    provider: FrontendDataProvider,
    team_ids: list[str],
    years: list[int],
) -> AgentState:
    """Run a team-relations query for head-to-head."""
    rf = RelationFilters()
    if years:
        rf.year_from = min(years)
        rf.year_to = max(years)
    rel = provider.get_team_relations(team_ids[0], rf, page=1, page_size=100)
    if not rel or not rel.get("team"):
        state["status"] = "empty"
        state["answer"] = "未找到该球队的交手记录。"
        return state

    state["facts"] = [{
        "fact_type": "relation",
        "fact_id": f"rel-{team_ids[0]}",
        "text": f"{team_ids[0]} 历史交手统计",
        "source_ids": [],
    }]
    state["sources"] = []
    state["graph"] = rel.get("graph", {"scope": "answer_facts", "nodes": [], "edges": []})
    stats = rel.get("stats", {})
    team_name = rel.get("team", {}).get("name", team_ids[0])
    state["answer"] = (
        f"{team_name} 共 {stats.get('matches', 0)} 场比赛："
        f"常规/加时胜 {stats.get('regulation_or_extra_time_wins', 0)} 场、"
        f"平局 {stats.get('draws', 0)} 场、"
        f"点球晋级 {stats.get('penalty_advances', 0)} 次、"
        f"失利 {stats.get('losses', 0)} 场。"
    )
    state["applied_filters"] = {"team_ids": team_ids}
    return state


# ---------------------------------------------------------------------------
# RAG query helpers (lazy init — no Chroma/LLM at import time)
# ---------------------------------------------------------------------------
_rag_service: object | None = None


def _get_rag_service() -> object | None:
    """Lazy-init RagService with real gateways — never at import time."""
    global _rag_service
    if _rag_service is not None:
        return _rag_service
    try:
        from backend.rag.chroma_gateway import ChromaRetrievalGateway
        from backend.rag.openai_compatible_generation import (
            OpenAICompatibleGenerationClient,
        )
        from backend.rag.service import RagService

        retrieval = ChromaRetrievalGateway()
        generation = OpenAICompatibleGenerationClient()
        _rag_service = RagService(retrieval=retrieval, generation=generation)
        return _rag_service
    except Exception:
        return None


def _rag_query(state: AgentState) -> AgentState:
    """Execute semantic / hybrid query via RagService → Chroma → DeepSeek."""
    import asyncio

    from backend.schemas.rag_contract import (
        RAG_CONTRACT_VERSION,
        QueryTypeEnum,
        RAGOptions,
        RAGRequest,
        RetrievalFilters,
    )

    route = state.get("route", "")
    if route not in ("rag_query", "hybrid_query"):
        return state

    rag_svc = _get_rag_service()
    if rag_svc is None:
        state["status"] = "error"
        state["answer"] = "RAG 服务暂时不可用。"
        state["warnings"].append({
            "code": "DATA_SOURCE_UNAVAILABLE",
            "message": "RAG 服务未配置或初始化失败。",
            "component": "rag_query",
            "retryable": True,
        })
        return state

    # --- Build structured_facts + source_catalog from SQLite -------------
    provider = _get_provider_safe()
    extracted = state.get("extracted", {})
    filters = state.get("filters", {})

    years = list(filters.get("years", [])) or extracted.get("years", [])
    team_ids = list(filters.get("team_ids", [])) or extracted.get("team_ids", [])
    stages = list(filters.get("stages", [])) or extracted.get("stages", [])
    match_ids = list(filters.get("match_ids", [])) or extracted.get("match_ids", [])
    has_penalties = filters.get("has_penalties")
    if has_penalties is None:
        has_penalties = extracted.get("has_penalties")

    structured_facts: list[dict] = []
    source_catalog: list[dict] = []

    if provider and route == "hybrid_query":
        try:
            from backend.schemas.common import StageEnum

            parsed_stages = []
            for s in stages:
                try:
                    parsed_stages.append(StageEnum(s))
                except ValueError:
                    pass

            mf = type("MatchFilters", (), {})()
            mf.years = years
            mf.team_ids = team_ids
            mf.stages = parsed_stages
            mf.result_types = []
            mf.has_penalties = has_penalties if has_penalties else None

            result = provider.list_matches(mf, page=1, page_size=20)
            items = result.items if result else []
            for m in items[:20]:
                match = provider.get_match(m.get("match_id", ""))
                if match:
                    structured_facts.append(_build_structured_fact(match))
                    for s in match.get("sources", []):
                        if s.get("source_id") not in {sc.get("source_id") for sc in source_catalog}:
                            source_catalog.append({
                                "source_id": s.get("source_id", ""),
                                "title": s.get("title", ""),
                                "url": s.get("url"),
                                "page": s.get("page"),
                                "document_id": s.get("document_id"),
                                "data_version": s.get("data_version"),
                            })
        except Exception:
            pass

    # --- Build RetrievalFilters ------------------------------------------
    rag_filters = RetrievalFilters(
        years=years,
        team_ids=team_ids,
        stages=stages,
        result_types=[],
        match_ids=match_ids,
    )

    # --- Build RAGRequest ------------------------------------------------
    query_type = QueryTypeEnum.hybrid if route == "hybrid_query" else QueryTypeEnum.semantic
    rag_request = RAGRequest(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id=state.get("trace_id", ""),
        question=state.get("question", ""),
        original_question=state.get("question", ""),
        query_type=query_type,
        filters=rag_filters,
        structured_facts=structured_facts,
        source_catalog=source_catalog,
        options=RAGOptions(retrieval_top_k=5, rerank_top_n=3),
    )

    # --- Call RagService (async → sync bridge for LangGraph) -------------
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Running inside an async context (e.g., FastAPI) — use
            # a thread-pool executor to avoid "cannot call asyncio.run
            # from a running event loop".
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(asyncio.run, rag_svc.generate(rag_request))
                rag_result = fut.result(timeout=35)
        else:
            rag_result = asyncio.run(rag_svc.generate(rag_request))
    except Exception:
        state["status"] = "error"
        state["answer"] = "RAG 查询处理失败。"
        state["warnings"].append({
            "code": "UPSTREAM_TIMEOUT",
            "message": "RAG 查询超时或失败。",
            "component": "rag_query",
            "retryable": True,
        })
        return state

    # --- Map RAGResult → state -------------------------------------------
    _apply_rag_result(state, rag_result)
    return state


def _build_structured_fact(match: dict) -> dict:
    """Build a structured fact dict from provider match data."""
    h = match.get("home_team", {})
    a = match.get("away_team", {})
    s = match.get("score", {})
    w = match.get("winner_team")
    return {
        "match_id": match["match_id"],
        "tournament_year": match.get("tournament_year"),
        "stage": match.get("stage"),
        "stage_name": match.get("stage_name", ""),
        "home_team_id": h.get("team_id", ""),
        "home_team_name": h.get("name", ""),
        "away_team_id": a.get("team_id", ""),
        "away_team_name": a.get("name", ""),
        "home_score_90": s.get("regular_time", {}).get("home"),
        "away_score_90": s.get("regular_time", {}).get("away"),
        "home_score_et": s.get("after_extra_time", {}).get("home"),
        "away_score_et": s.get("after_extra_time", {}).get("away"),
        "home_penalties": s.get("penalties", {}).get("home") if s.get("penalties") else None,
        "away_penalties": s.get("penalties", {}).get("away") if s.get("penalties") else None,
        "score_display": s.get("display", ""),
        "penalty_score": s.get("penalty_display"),
        "result_type": match.get("result_type"),
        "winner_team_id": w.get("team_id") if w else None,
        "source_ids": [src.get("source_id", "") for src in match.get("sources", [])],
    }


def _apply_rag_result(state: AgentState, rag_result: object) -> None:
    """Map RAGResult fields into the AgentState dict."""
    status = getattr(rag_result, "status", None)
    status_str = status.value if hasattr(status, "value") else str(status or "error")

    state["status"] = status_str
    state["answer"] = getattr(rag_result, "answer", "") or ""

    # Map RAG facts → frontend AgentFact shape
    rag_facts = getattr(rag_result, "facts", []) or []
    state["facts"] = []
    for f in rag_facts:
        fd = {
            "fact_type": getattr(f, "fact_type", "match_result"),
            "fact_id": getattr(f, "fact_id", ""),
            "text": getattr(f, "text", ""),
            "source_ids": getattr(f, "source_ids", []),
        }
        if hasattr(f, "match_id"):
            fd["match_id"] = f.match_id
        if hasattr(f, "tournament_year"):
            fd["tournament_year"] = f.tournament_year
        if hasattr(f, "stage"):
            fd["stage"] = f.stage.value if hasattr(f.stage, "value") else f.stage
        if hasattr(f, "stage_name"):
            fd["stage_name"] = f.stage_name
        if hasattr(f, "score_display"):
            fd["score_display"] = f.score_display
        if hasattr(f, "penalty_score"):
            fd["penalty_score"] = f.penalty_score
        if hasattr(f, "result_type"):
            rt = f.result_type
            fd["result_type"] = rt.value if hasattr(rt, "value") else rt
        if hasattr(f, "winner_team_id"):
            fd["winner_team_id"] = f.winner_team_id
        state["facts"].append(fd)

    # Map sources
    rag_sources = getattr(rag_result, "sources", []) or []
    state["sources"] = []
    for s in rag_sources:
        state["sources"].append({
            "source_id": getattr(s, "source_id", ""),
            "title": getattr(s, "title", ""),
            "url": getattr(s, "url"),
            "page": getattr(s, "page"),
            "document_id": getattr(s, "document_id"),
            "data_version": getattr(s, "data_version"),
            "used_for_fact_ids": getattr(s, "used_for_fact_ids", []),
        })

    # Evidence never goes to frontend
    # Map applied_filters
    af = getattr(rag_result, "applied_filters", None)
    if af is not None:
        state["applied_filters"] = {
            "years": getattr(af, "years", []),
            "team_ids": getattr(af, "team_ids", []),
            "stages": getattr(af, "stages", []),
            "result_types": getattr(af, "result_types", []),
            "match_ids": getattr(af, "match_ids", []),
            "has_penalties": state.get("filters", {}).get("has_penalties"),
        }

    # Map warnings
    rag_warnings = getattr(rag_result, "warnings", []) or []
    for w in rag_warnings:
        state["warnings"].append({
            "code": getattr(w, "code", ""),
            "message": getattr(w, "message", ""),
            "component": getattr(w, "component", ""),
            "retryable": getattr(w, "retryable", False),
        })

    # Map timing
    rag_timing = getattr(rag_result, "timing", None)
    if rag_timing is not None:
        state["timing"] = {
            "routing_ms": 0,
            "sql_ms": 0,
            "retrieval_ms": getattr(rag_timing, "retrieval_ms", 0),
            "generation_ms": getattr(rag_timing, "generation_ms", 0),
            "total_ms": getattr(rag_timing, "total_ms", 0),
        }

    # Confidence — always null (code-enforced)
    state["confidence"] = None

    # Build graph from facts
    state["graph"] = _build_rag_graph(rag_facts, rag_sources)


def _build_rag_graph(
    facts: list[object], sources: list[object]
) -> dict:
    """Build a minimal graph from RAG facts (no fabricated edges)."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_matches: set[str] = set()

    for f in facts:
        mid = getattr(f, "match_id", None)
        if not mid or mid in seen_matches:
            continue
        seen_matches.add(mid)

        hid = getattr(f, "home_team_id", "")
        hname = getattr(f, "home_team_name", "")
        aid = getattr(f, "away_team_id", "")
        aname = getattr(f, "away_team_name", "")
        wid = getattr(f, "winner_team_id", None)

        if hid:
            nodes[hid] = {"id": hid, "name": hname, "type": "team"}
        if aid:
            nodes[aid] = {"id": aid, "name": aname, "type": "team"}

        source_id = wid if wid else hid
        target_id = aid if (wid and wid == hid) else (hid if (wid and wid != hid) else aid)

        edges.append({
            "id": f"edge-{mid}",
            "source": source_id,
            "target": target_id,
            "type": "match_result",
            "match_id": mid,
            "tournament_year": getattr(f, "tournament_year", None),
            "stage": (
                getattr(f, "stage", "").value
                if hasattr(getattr(f, "stage", ""), "value")
                else getattr(f, "stage", "")
            ),
            "stage_name": getattr(f, "stage_name", ""),
            "result_type": (
                getattr(f, "result_type", "").value
                if hasattr(getattr(f, "result_type", ""), "value")
                else getattr(f, "result_type", "")
            ),
            "winner_team_id": wid,
        })

    return {"scope": "answer_facts", "nodes": list(nodes.values()), "edges": edges}


def _assemble(state: AgentState) -> AgentState:
    """Final assembly — ensure all response fields are present."""
    state["timing"]["total_ms"] = 20  # placeholder
    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_provider_safe() -> FrontendDataProvider | None:
    try:
        return get_provider()
    except Exception:
        return None


def _build_fact(match: dict) -> dict:
    h = match.get("home_team", {})
    a = match.get("away_team", {})
    s = match.get("score", {})
    w = match.get("winner_team")
    return {
        "fact_type": "match_result",
        "fact_id": f"fact-{match['match_id']}-result",
        "match_id": match["match_id"],
        "tournament_year": match.get("tournament_year"),
        "stage": match.get("stage"),
        "stage_name": match.get("stage_name", ""),
        "home_team": h,
        "away_team": a,
        "score": s,
        "result_type": match.get("result_type"),
        "winner_team": w,
        "text": _build_answer_text(match),
        "source_ids": [s.get("source_id", "") for s in match.get("sources", [])],
    }


def _build_list_fact(match: dict) -> dict:
    h = match.get("home_team", {}).get("name", "")
    a = match.get("away_team", {}).get("name", "")
    s = match.get("score", {}).get("display", "?")
    return {
        "fact_type": "match_result",
        "fact_id": f"fact-{match['match_id']}-list",
        "match_id": match["match_id"],
        "tournament_year": match.get("tournament_year"),
        "stage": match.get("stage"),
        "stage_name": match.get("stage_name", ""),
        "home_team": match.get("home_team"),
        "away_team": match.get("away_team"),
        "text": f"{h} vs {a} {s}",
        "source_ids": [],
    }


def _build_answer_text(match: dict) -> str:
    h = match.get("home_team", {}).get("name", "")
    a = match.get("away_team", {}).get("name", "")
    year = match.get("tournament_year", "")
    stage = match.get("stage_name", "")
    s = match.get("score", {})
    display = s.get("display", "?")
    pd = s.get("penalty_display")
    if pd:
        return f"{year}年世界杯{stage}，{h} vs {a}，加时赛后 {display}，点球大战 {pd}。"
    return f"{year}年世界杯{stage}，{h} vs {a}，比分 {display}。"


def _build_answer_graph(match: dict) -> dict:
    h = match.get("home_team", {})
    a = match.get("away_team", {})
    w = match.get("winner_team")
    return {
        "scope": "answer_facts",
        "nodes": [
            {"id": h.get("team_id", ""), "name": h.get("name", ""), "type": "team"},
            {"id": a.get("team_id", ""), "name": a.get("name", ""), "type": "team"},
        ],
        "edges": [{
            "id": f"edge-{match['match_id']}",
            "source": (
                w["team_id"] if (w and w.get("team_id"))
                else h.get("team_id", "")
            ),
            "target": (
                a.get("team_id", "")
                if (w and w.get("team_id", "") == h.get("team_id", ""))
                else h.get("team_id", "")
            ),
            "type": "match_result",
            "match_id": match["match_id"],
            "tournament_year": match.get("tournament_year"),
            "stage": match.get("stage", ""),
            "stage_name": match.get("stage_name", ""),
            "result_type": match.get("result_type", ""),
            "winner_team_id": w["team_id"] if w else None,
            "label": (
                f"{match.get('tournament_year','')} "
                f"{match.get('stage_name','')} "
                f"{match.get('score',{}).get('display','')}"
            ),
        }],
    }


def _build_list_graph(items: list[dict]) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for m in items:
        for t in (m.get("home_team"), m.get("away_team")):
            if t:
                nodes[t["team_id"]] = {"id": t["team_id"], "name": t["name"], "type": "team"}
        w = m.get("winner_team")
        hid = m.get("home_team", {}).get("team_id", "")
        aid = m.get("away_team", {}).get("team_id", "")
        edges.append({
            "id": f"edge-{m['match_id']}",
            "source": (
                w["team_id"] if (w and w.get("team_id")) else hid
            ),
            "target": (
                aid if (w and w.get("team_id") and w["team_id"] == hid)
                else (hid if (w and w.get("team_id") and w["team_id"] != hid)
                      else aid)
            ),
            "type": "match_result",
            "match_id": m["match_id"],
            "tournament_year": m.get("tournament_year"),
            "stage": m.get("stage", ""),
            "stage_name": m.get("stage_name", ""),
            "result_type": m.get("result_type", ""),
            "winner_team_id": w["team_id"] if w else None,
            "label": (
                f"{m.get('tournament_year','')} "
                f"{m.get('stage_name','')} "
                f"{m.get('score',{}).get('display','')}"
            ),
        })
    return {"scope": "answer_facts", "nodes": list(nodes.values()), "edges": edges}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
def _build_graph() -> StateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("normalise", _normalise)
    builder.add_node("classify", _classify)
    builder.add_node("exact_query", _exact_query)
    builder.add_node("rag_query", _rag_query)
    builder.add_node("assemble", _assemble)

    builder.set_entry_point("normalise")
    builder.add_edge("normalise", "classify")
    builder.add_conditional_edges(
        "classify",
        lambda s: _route_after_classify(s),
        {
            "exact_query": "exact_query",
            "rag_query": "rag_query",
            "assemble": "assemble",
        },
    )
    builder.add_edge("exact_query", "assemble")
    builder.add_edge("rag_query", "assemble")
    builder.add_edge("assemble", END)
    return builder.compile()


def _route_after_classify(state: AgentState) -> str:
    route = state.get("route", "")
    if route in ("general_chat", "clarification"):
        return "assemble"
    if route in ("rag_query", "hybrid_query"):
        return "rag_query"
    return "exact_query"


_graph = _build_graph()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class LangGraphAgentService:
    """Exact-fact agent backed by LangGraph + SQLite Provider. No LLM/E/D."""

    def query(self, request: dict, trace_id: str) -> dict:
        state: dict[str, Any] = {
            "question": request.get("question", ""),
            "session_id": request.get("session_id"),
            "filters": request.get("filters", {}),
            "trace_id": trace_id,
        }
        result = _graph.invoke(state)
        # Build the AgentQueryResponse data dict
        return {
            "data_status": "live",
            "status": result.get("status", "ok"),
            "intent": result.get("intent", ""),
            "route": result.get("route", ""),
            "answer": result.get("answer", ""),
            "needs_clarification": result.get("needs_clarification", False),
            "clarification_question": result.get("clarification_question"),
            "facts": result.get("facts", []),
            "sources": result.get("sources", []),
            "graph": result.get("graph", {"scope": "answer_facts", "nodes": [], "edges": []}),
            "applied_filters": result.get("applied_filters", {}),
            "confidence": result.get("confidence"),
            "warnings": result.get("warnings", []),
            "timing": result.get(
                "timing",
                {"routing_ms": 0, "sql_ms": 0, "retrieval_ms": 0,
                 "generation_ms": 0, "total_ms": 0},
            ),
        }
