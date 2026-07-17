"""
事实文本生成器 v2

对齐 RAG 接口契约 rag-v1.0-draft：
- 输出格式为 StructuredFact（含 document_id、checksum、source_ids 数组）
- fact_text 将年份、阶段、双方、90分钟比分、加时比分、点球比分和胜者合并在一条事实中
- 支持 match_facts.jsonl 格式输出
"""

import hashlib
import json
from typing import Optional

from models.entities import Match, Team, StructuredFact


# ═══════════════════════════════════════════════════════════
#  单场比赛事实文本
# ═══════════════════════════════════════════════════════════

def generate_match_fact(
    match: Match,
    home_team: Team,
    away_team: Team,
    tournament_host: str = "",
) -> str:
    """
    为一场比赛生成标准化中文事实文本。

    根据 result_type 选择不同模板：
    - regulation:  "2018年世界杯决赛，法国队在卢日尼基体育场以4:2战胜克罗地亚队。"
    - extra_time:  "……90分钟内1:1战平，加时赛后法国队以2:1获胜。"
    - penalties:   "……90分钟2:2、加时赛后3:3均战平，点球大战阿根廷队4:2胜出。"
    - draw:        "……双方1:1战平。"

    返回的文本长度控制在 80-200 字，适合作为单个 Chroma chunk。
    """
    year = match.tournament_year
    stage_name = match.stage_name or match.stage
    venue = match.venue or ""

    home_name = home_team.canonical_name
    away_name = away_team.canonical_name

    result_type = match.result_type
    venue_str = f"在{venue}" if venue else ""

    if result_type == "regulation":
        if match.winner_team_id == home_team.team_id:
            return (
                f"{year}年世界杯{stage_name}，{home_name}队{venue_str}"
                f"以{match.score_display}战胜{away_name}队，常规时间结束即分出胜负。"
            )
        else:
            rev_score = f"{match.away_score_90}:{match.home_score_90}"
            return (
                f"{year}年世界杯{stage_name}，{away_name}队{venue_str}"
                f"以{rev_score}战胜{home_name}队，常规时间结束即分出胜负。"
            )

    elif result_type == "extra_time":
        score_90 = f"{match.home_score_90}:{match.away_score_90}"
        winner_name = home_name if match.winner_team_id == home_team.team_id else away_name
        return (
            f"{year}年世界杯{stage_name}，{home_name}队{venue_str}与{away_name}队"
            f"90分钟内{score_90}战平，加时赛后{winner_name}队以{match.score_display}获胜。"
        )

    elif result_type == "penalties":
        h_pen = match.home_penalties or 0
        a_pen = match.away_penalties or 0
        pen_score = f"{h_pen}:{a_pen}"
        winner_name = home_name if h_pen > a_pen else away_name
        score_90 = f"{match.home_score_90}:{match.away_score_90}"
        if match.home_score_et is not None and match.away_score_et is not None:
            if match.home_score_et != match.home_score_90 or match.away_score_et != match.away_score_90:
                score_et = f"{match.home_score_et}:{match.away_score_et}"
                return (
                    f"{year}年世界杯{stage_name}，{home_name}队{venue_str}与{away_name}队"
                    f"90分钟内{score_90}战平、加时赛后{score_et}仍战平，"
                    f"点球大战{winner_name}队{pen_score}胜出晋级。"
                )
        return (
            f"{year}年世界杯{stage_name}，{home_name}队{venue_str}与{away_name}队"
            f"90分钟内{score_90}战平，"
            f"点球大战{winner_name}队{pen_score}胜出晋级。"
        )

    else:  # draw
        return (
            f"{year}年世界杯{stage_name}，{home_name}队{venue_str}"
            f"与{away_name}队{match.score_display}战平。"
        )


# ═══════════════════════════════════════════════════════════
#  转换为 StructuredFact（对齐 RAG 契约）
# ═══════════════════════════════════════════════════════════

def match_to_structured_fact(
    match: Match,
    home_team: Team,
    away_team: Team,
    source_ids: Optional[list[str]] = None,
    tournament_host: str = "",
) -> StructuredFact:
    """
    将 Match + Team 转为 StandardizedFact，对齐 RAGRequest.StructuredFact 格式。

    每条 fact 包含：
    - document_id、match_id、年份、阶段、球队ID/名称
    - 90分钟/加时/点球比分
    - score_display 和 penalty_score（独立字段）
    - result_type、winner_team_id
    - fact_text（完整叙述）
    - source_ids（数组）、data_version、checksum
    """
    if source_ids is None:
        source_ids = []

    fact_text = generate_match_fact(match, home_team, away_team, tournament_host)

    # 生成 document_id
    document_id = f"match-fact:{match.match_id}:{match.data_version or 'v2'}"

    # 生成 checksum
    checksum = _compute_fact_checksum(fact_text, match.match_id)

    return StructuredFact(
        match_id=match.match_id,
        document_id=document_id,
        tournament_year=match.tournament_year,
        match_date=match.match_date,
        stage=match.stage,
        stage_name=match.stage_name or match.stage,
        home_team_id=match.home_team_id,
        home_team_name=home_team.canonical_name,
        away_team_id=match.away_team_id,
        away_team_name=away_team.canonical_name,
        home_score_90=match.home_score_90,
        away_score_90=match.away_score_90,
        home_score_et=match.home_score_et,
        away_score_et=match.away_score_et,
        home_penalties=match.home_penalties,
        away_penalties=match.away_penalties,
        score_display=match.score_display,
        penalty_score=match.penalty_score,
        result_type=match.result_type,
        winner_team_id=match.winner_team_id,
        fact_text=fact_text,
        source_ids=source_ids,
        data_version=match.data_version or "v2",
        checksum=checksum,
    )


# ═══════════════════════════════════════════════════════════
#  批量生成（供 Chroma 入库 / D 消费）
# ═══════════════════════════════════════════════════════════

def generate_all_match_facts(
    matches: list[Match],
    teams: dict[str, Team],
    source_id: str = "",
    source_url: str = "",
    source_page: Optional[str] = None,
    tournament_host: str = "",
) -> list[dict]:
    """
    为所有比赛生成 Chroma 入库格式的事实文本。

    ═══════════════════════════════════════════════════════
    这是 C → D 的接口契约：match_facts.jsonl
    ═══════════════════════════════════════════════════════

    每条记录格式（Chroma 标准摄入格式）：
    {
        "id": "match_fact_M-2018-64_v1",           // 幂等更新 key
        "text": "2018年世界杯决赛，法国队...",       // 向量化文本
        "metadata": {
            "match_id": "M-2018-64",
            "tournament_year": 2018,
            "stage": "决赛",
            "team_ids": ["team_FRA", "team_CRO"],   // 数组或序列化字符串
            "result_type": "regulation",

            "source_id": "src_csv_20260716_001",     // 必须保留，进入最终响应
            "document_name": "FIFA World Cup 2018",
            "source_url": "https://...",             // 可追溯 URL
            "source_page": null,                     // PDF 页码

            "chunk_index": 0,                        // 长文档切片定位
            "language": "zh",
            "data_version": "2026-07-16-v1"          // 实验复现用
        }
    }

    注意：
    - D 需确认 Chroma 版本是否支持 team_ids 数组；不支持则序列化为逗号分隔字符串
    - source_id 必须在全链路保留，最终进入 E→B 的 sources
    """
    results = []
    for match in matches:
        home_team = teams.get(match.home_team_id)
        away_team = teams.get(match.away_team_id)

        if not home_team or not away_team:
            continue

        fact_text = generate_match_fact(match, home_team, away_team, tournament_host)

        # 生成幂等 id
        doc_id = f"match_fact_{match.match_id}_{match.data_version or 'v1'}"

        results.append({
            "id": doc_id,
            "text": fact_text,
            "metadata": {
                "match_id": match.match_id,
                "tournament_year": match.tournament_year,
                "stage": match.stage_name or match.stage,
                "team_ids": [match.home_team_id, match.away_team_id],
                "result_type": match.result_type,

                "source_id": source_id,
                "document_name": f"FIFA World Cup {match.tournament_year}",
                "source_url": source_url,
                "source_page": source_page,

                "chunk_index": 0,
                "language": "zh",
                "data_version": match.data_version or "2026-07-16-v1",
            },
        })

    return results


# ═══════════════════════════════════════════════════════════
#  JSONL 格式输出（按 RAG 契约要求）
# ═══════════════════════════════════════════════════════════

def write_match_facts_jsonl(facts: list[dict], output_path: str) -> str:
    """
    将事实列表写入 JSONL 文件（每行一个 JSON）。
    这是整改清单要求的 match_facts.jsonl 格式。
    """
    from pathlib import Path
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for fact in facts:
            f.write(json.dumps(fact, ensure_ascii=False) + "\n")

    return str(path.resolve())


def write_match_facts_json(facts: list[dict], output_path: str) -> str:
    """
    将事实列表写入 JSON 文件（美化格式，用于人工查阅）。
    """
    from pathlib import Path
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

    return str(path.resolve())


# ═══════════════════════════════════════════════════════════
#  赛事概述（保留）
# ═══════════════════════════════════════════════════════════

def generate_tournament_summary(
    year: int,
    host: str,
    matches: list[Match],
    teams: dict[str, Team],
    champion: Optional[str] = None,
) -> str:
    """生成一届世界杯的概述文本。"""
    if not matches:
        return f"{year}年世界杯（主办国：{host}），暂无比赛数据。"

    total_goals = sum(
        (m.home_score_90 + m.away_score_90) for m in matches
    )
    unique_teams = set()
    for m in matches:
        unique_teams.add(m.home_team_id)
        unique_teams.add(m.away_team_id)

    finals = [m for m in matches if m.stage == "final"]
    final_str = ""
    if finals and champion:
        final = finals[0]
        final_str = f"决赛中{champion}以{final.score_display}获胜夺冠。"
    elif finals:
        final = finals[0]
        home_name = teams.get(final.home_team_id, Team(
            team_id=final.home_team_id, canonical_name=final.home_team_id
        )).canonical_name
        away_name = teams.get(final.away_team_id, Team(
            team_id=final.away_team_id, canonical_name=final.away_team_id
        )).canonical_name
        final_str = f"决赛在{home_name}与{away_name}之间进行，比分{final.score_display}。"

    return (
        f"{year}年世界杯在{host}举办，共{len(unique_teams)}支球队参赛，"
        f"进行了{len(matches)}场比赛，总进球{total_goals}个。{final_str}"
    )


# ═══════════════════════════════════════════════════════════
#  内部工具
# ═══════════════════════════════════════════════════════════

def _compute_fact_checksum(fact_text: str, match_id: str) -> str:
    """计算单条事实文本的 MD5 checksum（前 8 位）。"""
    content = f"{match_id}|{fact_text}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:8]
