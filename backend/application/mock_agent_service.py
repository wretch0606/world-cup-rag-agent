"""MockAgentService — deterministic mock for A↔B integration testing.

Four branches:
  1. Known 2022 final → status=ok with facts from Provider
  2. Missing year in "决赛" query → clarification_required
  3. Greeting / general chat → general_chat
  4. Unknown → empty
"""

from __future__ import annotations

from backend.dependencies import get_provider


class MockAgentService:
    """Deterministic mock agent — no LLM, no LangGraph, no Chroma."""

    def query(self, request: dict, trace_id: str) -> dict:
        question = request.get("question", "").strip()
        filters = request.get("filters", {})

        base = {
            "data_status": "mock",
            "status": "ok",
            "intent": "",
            "route": "",
            "answer": "",
            "needs_clarification": False,
            "clarification_question": None,
            "facts": [],
            "sources": [],
            "graph": {"scope": "answer_facts", "nodes": [], "edges": []},
            "applied_filters": filters,
            "confidence": None,
            "warnings": [{
                "code": "MOCK_DATA",
                "message": "当前为前端联调 Mock 响应，尚未接入真实 C/D/E 与 LangGraph。",
                "component": "mock_agent_service",
            }],
            "timing": {"routing_ms": 1, "sql_ms": 0, "retrieval_ms": 0, "generation_ms": 0, "total_ms": 0},
        }

        # Branch 1: Greeting
        if any(kw in question for kw in ["你好", "hello", "hi", "帮助"]):
            base["intent"] = "general_chat"
            base["route"] = "general_chat"
            base["answer"] = "你好！我是世界杯知识问答助手，可以回答关于世界杯比赛、比分、球队和晋级关系的问题。"
            base["timing"]["total_ms"] = 2
            return base

        # Branch 2: 2022 final exact fact
        if ("2022" in question or "卡塔尔" in question) and ("决赛" in question or "final" in question.lower()):
            base["intent"] = "match_result_query"
            base["route"] = "structured_query"
            base["answer"] = "2022年世界杯决赛，阿根廷与法国在90分钟内战成2:2，加时赛后为3:3；阿根廷在点球大战中以4:2获胜。"
            try:
                provider = get_provider()
                match = provider.get_match("M-2022-64")
                if match:
                    base["facts"] = [{
                        "fact_type": "match_result",
                        "fact_id": "fact-M-2022-64-result",
                        "match_id": match["match_id"],
                        "tournament_year": match["tournament_year"],
                        "stage": match["stage"],
                        "stage_name": match.get("stage_name", "决赛"),
                        "home_team": match["home_team"],
                        "away_team": match["away_team"],
                        "score": match["score"],
                        "result_type": match["result_type"],
                        "winner_team": match.get("winner_team"),
                        "text": "双方加时赛后战成3:3，阿根廷点球大战4:2获胜。",
                        "source_ids": ["src-mock-001"],
                    }]
                    base["sources"] = match.get("sources", [])
                    base["graph"] = {
                        "scope": "answer_facts",
                        "nodes": [
                            {"id": match["home_team"]["team_id"], "name": match["home_team"]["name"], "type": "team"},
                            {"id": match["away_team"]["team_id"], "name": match["away_team"]["name"], "type": "team"},
                        ],
                        "edges": [{
                            "id": f"edge-{match['match_id']}",
                            "source": match["home_team"]["team_id"],
                            "target": match["away_team"]["team_id"],
                            "type": "match_result",
                            "match_id": match["match_id"],
                            "tournament_year": match["tournament_year"],
                            "stage": match["stage"],
                            "stage_name": match.get("stage_name", ""),
                            "result_type": match["result_type"],
                            "winner_team_id": match.get("winner_team", {}).get("team_id") if match.get("winner_team") else None,
                            "label": f"{match['tournament_year']} {match.get('stage_name','')} {match['score']['display']}",
                        }],
                    }
            except Exception:
                pass
            base["timing"]["total_ms"] = 10
            return base

        # Branch 3: Missing year — clarification
        if "决赛" in question and not any(str(y) in question for y in range(1930, 2030, 4)):
            base["status"] = "clarification_required"
            base["intent"] = "match_result_query"
            base["route"] = "clarification"
            base["answer"] = "请补充世界杯年份。"
            base["needs_clarification"] = True
            base["clarification_question"] = "你想查询哪一届世界杯决赛？"
            base["warnings"].append({
                "code": "NEED_CLARIFICATION",
                "message": "年份条件不足。",
                "component": "routing",
                "retryable": False,
            })
            base["timing"]["total_ms"] = 2
            return base

        # Branch 4: Unknown — empty
        base["status"] = "empty"
        base["intent"] = "out_of_scope"
        base["route"] = "structured_query"
        base["answer"] = "当前知识库中没有足够信息回答您的问题。"
        base["warnings"].append({
            "code": "NO_RESULT",
            "message": "没有可靠事实或证据回答该问题。",
            "component": "mock_agent_service",
            "retryable": False,
        })
        base["timing"]["total_ms"] = 3
        return base
