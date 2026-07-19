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
    state.setdefault("timing", {"routing_ms": 0, "sql_ms": 0, "retrieval_ms": 0, "generation_ms": 0, "total_ms": 0})
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
    ask_about_score = any(kw in question for kw in ["比分", "结果", "谁赢", "获胜", "战胜", "击败", "几比几"])
    ask_about_matches = any(kw in question for kw in ["哪些比赛", "什么比赛", "有哪些比赛", "比赛列表", "交手", "交锋", "对", "交手过", "击败过", "战胜过"])
    ask_about_detail = any(kw in question for kw in ["详情", "细节", "情况", "介绍"])

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
        af = {"years": years, "team_ids": team_ids, "stages": stages, "has_penalties": has_penalties}
        state["applied_filters"] = af
        state["warnings"].append({
            "code": "NO_RESULT",
            "message": "没有可靠事实或证据回答该问题。",
            "component": "exact_query",
            "retryable": False,
        })
        return state

    # If exactly one match and question asks for score → return detail
    ask_score = any(kw in state.get("question", "") for kw in ["比分", "结果", "谁赢", "获胜", "几比几"])
    if len(items) == 1 and ask_score:
        match = provider.get_match(items[0]["match_id"]) if provider else None
        if match:
            state["facts"] = [_build_fact(match)]
            state["sources"] = match.get("sources", [])
            state["graph"] = _build_answer_graph(match)
            state["answer"] = _build_answer_text(match)
            state["applied_filters"] = {"years": years, "team_ids": team_ids, "stages": stages, "has_penalties": has_penalties}
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
            m.get("home_team", {}).get("name", "") or m.get("away_team", {}).get("name", "")
            for m in items
        ))
        state["answer"] = f"共找到 {len(items)} 场比赛{('（涉及 ' + teams_str + '）') if teams_str else ''}。"
    state["graph"] = _build_list_graph(items)
    state["applied_filters"] = {"years": years, "team_ids": team_ids, "stages": stages, "has_penalties": has_penalties}

    return state


def _run_relation_query(state: AgentState, provider: FrontendDataProvider, team_ids: list[str], years: list[int]) -> AgentState:
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

    state["facts"] = [
        {"fact_type": "relation", "fact_id": f"rel-{team_ids[0]}", "text": f"{team_ids[0]} 历史交手统计", "source_ids": []}
    ]
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
            "source": w["team_id"] if w else h.get("team_id", ""),
            "target": a.get("team_id", "") if (w and w["team_id"] == h.get("team_id", "")) else (h.get("team_id", "") if not w else h.get("team_id", "")),
            "type": "match_result",
            "match_id": match["match_id"],
            "tournament_year": match.get("tournament_year"),
            "stage": match.get("stage", ""),
            "stage_name": match.get("stage_name", ""),
            "result_type": match.get("result_type", ""),
            "winner_team_id": w["team_id"] if w else None,
            "label": f"{match.get('tournament_year','')} {match.get('stage_name','')} {match.get('score',{}).get('display','')}",
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
            "source": w["team_id"] if w else hid,
            "target": aid if (w and w["team_id"] == hid) else (hid if not w else hid),
            "type": "match_result",
            "match_id": m["match_id"],
            "tournament_year": m.get("tournament_year"),
            "stage": m.get("stage", ""),
            "stage_name": m.get("stage_name", ""),
            "result_type": m.get("result_type", ""),
            "winner_team_id": w["team_id"] if w else None,
            "label": f"{m.get('tournament_year','')} {m.get('stage_name','')} {m.get('score',{}).get('display','')}",
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
    builder.add_node("assemble", _assemble)

    builder.set_entry_point("normalise")
    builder.add_edge("normalise", "classify")
    builder.add_conditional_edges(
        "classify",
        lambda s: "exact_query" if s["route"] not in ("general_chat", "clarification") else "assemble",
        {"exact_query": "exact_query", "assemble": "assemble"},
    )
    builder.add_edge("exact_query", "assemble")
    builder.add_edge("assemble", END)
    return builder.compile()


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
            "timing": result.get("timing", {"routing_ms": 0, "sql_ms": 0, "retrieval_ms": 0, "generation_ms": 0, "total_ms": 0}),
        }
