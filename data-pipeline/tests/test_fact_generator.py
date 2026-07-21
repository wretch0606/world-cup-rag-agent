"""
事实文本生成器测试 v2

对齐 v2 更新：
- generate_all_match_facts 使用 source_ids 列表保留多个数据来源
- 输出格式改为 Chroma 摄入格式 {id, text, metadata{}}
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.entities import Match, Team
from services.fact_generator import (
    generate_all_match_facts,
    generate_match_fact,
    generate_tournament_summary,
)

# ── 测试用 Team ─────────────────────────────────────

TEAM_FRA = Team(team_id="team_FRA", canonical_name="法国", confederation="UEFA")
TEAM_CRO = Team(team_id="team_CRO", canonical_name="克罗地亚", confederation="UEFA")
TEAM_BEL = Team(team_id="team_BEL", canonical_name="比利时", confederation="UEFA")
TEAM_ENG = Team(team_id="team_ENG", canonical_name="英格兰", confederation="UEFA")
TEAM_ARG = Team(team_id="team_ARG", canonical_name="阿根廷", confederation="CONMEBOL")


# ── 事实文本生成 ────────────────────────────────────


class TestGenerateMatchFact:
    def test_regulation_fact(self):
        match = Match(
            match_id="WC2018_FRA_CRO_final",
            tournament_year=2018,
            match_date="2018-07-15",
            stage="final",
            stage_name="决赛",
            venue="卢日尼基体育场",
            home_team_id="team_FRA",
            away_team_id="team_CRO",
            home_score_90=4,
            away_score_90=2,
            winner_team_id="team_FRA",
            result_type="regulation",
            score_display="4:2",
        )
        fact = generate_match_fact(match, TEAM_FRA, TEAM_CRO)
        assert "2018" in fact
        assert "法国" in fact
        assert "克罗地亚" in fact
        assert "4:2" in fact
        assert "常规时间" in fact

    def test_extra_time_fact(self):
        match = Match(
            match_id="WC2018_CRO_ENG_semi",
            tournament_year=2018,
            match_date="2018-07-11",
            stage="semi_final",
            stage_name="半决赛",
            venue="卢日尼基体育场",
            home_team_id="team_CRO",
            away_team_id="team_ENG",
            home_score_90=1,
            away_score_90=1,
            home_score_et=2,
            away_score_et=1,
            winner_team_id="team_CRO",
            result_type="extra_time",
            score_display="2:1",
        )
        fact = generate_match_fact(match, TEAM_CRO, TEAM_ENG)
        assert "加时" in fact
        assert "战平" in fact

    def test_penalties_fact(self):
        match = Match(
            match_id="WC2022_ARG_FRA_final",
            tournament_year=2022,
            match_date="2022-12-18",
            stage="final",
            stage_name="决赛",
            venue="卢赛尔体育场",
            home_team_id="team_ARG",
            away_team_id="team_FRA",
            home_score_90=2,
            away_score_90=2,
            home_score_et=3,
            away_score_et=3,
            home_penalties=4,
            away_penalties=2,
            winner_team_id="team_ARG",
            result_type="penalties",
            score_display="3:3",
            penalty_score="4:2",
        )
        fact = generate_match_fact(match, TEAM_ARG, TEAM_FRA)
        assert "点球" in fact
        assert "阿根廷" in fact

    def test_draw_fact(self):
        match = Match(
            match_id="WC2018_POR_ESP_group",
            tournament_year=2018,
            match_date="2018-06-15",
            stage="group",
            stage_name="小组赛",
            home_team_id="team_POR",
            away_team_id="team_ESP",
            home_score_90=3,
            away_score_90=3,
            winner_team_id=None,
            result_type="draw",
            score_display="3:3",
        )
        fact = generate_match_fact(
            match,
            Team(team_id="team_POR", canonical_name="葡萄牙"),
            Team(team_id="team_ESP", canonical_name="西班牙"),
        )
        assert "战平" in fact


class TestGenerateTournamentSummary:
    def test_summary_with_data(self):
        matches = [
            Match(
                match_id="WC2018_FRA_CRO_final",
                tournament_year=2018,
                match_date="2018-07-15",
                stage="final",
                stage_name="决赛",
                home_team_id="team_FRA",
                away_team_id="team_CRO",
                home_score_90=4,
                away_score_90=2,
                winner_team_id="team_FRA",
                result_type="regulation",
                score_display="4:2",
            ),
            Match(
                match_id="WC2018_BEL_ENG_3rd",
                tournament_year=2018,
                match_date="2018-07-14",
                stage="third_place",
                stage_name="三四名决赛",
                home_team_id="team_BEL",
                away_team_id="team_ENG",
                home_score_90=2,
                away_score_90=0,
                winner_team_id="team_BEL",
                result_type="regulation",
                score_display="2:0",
            ),
        ]
        teams = {
            "team_FRA": TEAM_FRA,
            "team_CRO": TEAM_CRO,
            "team_BEL": TEAM_BEL,
            "team_ENG": TEAM_ENG,
        }
        summary = generate_tournament_summary(2018, "俄罗斯", matches, teams, champion="法国")
        assert "2018" in summary
        assert "俄罗斯" in summary


class TestGenerateAllMatchFacts:
    def test_batch_generation(self):
        """v2: 输出 Chroma 摄入格式 {id, text, metadata{}}"""
        matches = [
            Match(
                match_id="WC2018_FRA_CRO_final",
                tournament_year=2018,
                match_date="2018-07-15",
                stage="final",
                stage_name="决赛",
                home_team_id="team_FRA",
                away_team_id="team_CRO",
                home_score_90=4,
                away_score_90=2,
                winner_team_id="team_FRA",
                result_type="regulation",
                score_display="4:2",
                data_version="2026-07-16-v2",
            ),
        ]
        teams = {"team_FRA": TEAM_FRA, "team_CRO": TEAM_CRO}
        results = generate_all_match_facts(
            matches,
            teams,
            source_ids=["src_test_001"],
            source_url="https://example.org/test",
            source_page=None,
            tournament_host="俄罗斯",
        )
        assert len(results) == 1
        record = results[0]
        # v2 Chroma 格式
        assert "id" in record
        assert record["id"] == "match_fact_WC2018_FRA_CRO_final_2026-07-16-v2"
        assert "text" in record
        assert "metadata" in record
        assert record["metadata"]["document_id"] == record["id"]
        assert record["metadata"]["match_id"] == "WC2018_FRA_CRO_final"
        assert record["metadata"]["result_type"] == "regulation"
        assert record["metadata"]["source_ids"] == ["src_test_001"]
        assert record["metadata"]["source_url"] == "https://example.org/test"
        assert record["metadata"]["source_page"] is None
        assert record["metadata"]["chunk_index"] == 0
        assert record["metadata"]["language"] == "zh"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
