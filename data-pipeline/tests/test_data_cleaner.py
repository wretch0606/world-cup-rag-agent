"""
数据清洗器测试 v2

对齐 v2 更新：
- normalize_stage 返回 (enum, stage_name) 元组
- generate_score_display 返回 (score_display, penalty_score) 元组
- STAGE_MAPPING 改为从 stage_mapping.json 加载
- clean_match_record 参数 source_id → source_ids
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.data_cleaner import (
    load_team_aliases,
    normalize_team_name,
    normalize_stage,
    normalize_date,
    determine_result_type,
    generate_score_display,
    validate_score_consistency,
    clean_match_record,
    _load_stage_mapping,
)


# ── 球队别名 ────────────────────────────────────────

class TestLoadTeamAliases:
    def test_load_valid_file(self):
        alias_file = Path(__file__).parent.parent / "data" / "team_aliases.json"
        data = load_team_aliases(str(alias_file))
        assert "alias_map" in data
        assert "team_info" in data
        assert data["alias_map"]["法国"] == "team_FRA"
        assert data["alias_map"]["France"] == "team_FRA"

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_team_aliases("不存在的文件.json")


class TestNormalizeTeamName:
    @pytest.fixture(autouse=True)
    def setup(self):
        alias_file = Path(__file__).parent.parent / "data" / "team_aliases.json"
        self.alias_data = load_team_aliases(str(alias_file))

    def test_exact_match_chinese(self):
        tid, warn = normalize_team_name("法国", self.alias_data["alias_map"])
        assert tid == "team_FRA"
        assert warn is None

    def test_exact_match_english(self):
        tid, warn = normalize_team_name("France", self.alias_data["alias_map"])
        assert tid == "team_FRA"
        assert warn is None

    def test_fuzzy_match(self):
        tid, warn = normalize_team_name("荷兰队", self.alias_data["alias_map"])
        assert tid == "team_NED"

    def test_unknown_team(self):
        tid, warn = normalize_team_name("火星队", self.alias_data["alias_map"])
        assert tid is None

    def test_empty_name(self):
        tid, warn = normalize_team_name("", self.alias_data["alias_map"])
        assert tid is None


# ── 阶段归一 ────────────────────────────────────────

class TestNormalizeStage:
    def test_known_stages(self):
        """v2: normalize_stage 返回 (enum, display_name) 元组"""
        enum, name = normalize_stage("final")
        assert enum == "final"
        assert name == "决赛"

        enum, name = normalize_stage("Final")
        assert enum == "final"

        enum, name = normalize_stage("决赛")
        assert enum == "final"
        assert name == "决赛"

        enum, name = normalize_stage("semi-final")
        assert enum == "semi_final"
        assert name == "半决赛"

        enum, name = normalize_stage("quarterfinal")
        assert enum == "quarter_final"

        enum, name = normalize_stage("小组赛")
        assert enum == "group"
        assert name == "小组赛"

        enum, name = normalize_stage("round of 16")
        assert enum == "round_of_16"
        assert name == "1/8决赛"

    def test_unknown_stage(self):
        enum, name = normalize_stage("神秘阶段")
        assert enum == "神秘阶段"  # 无法识别时保留原值

    def test_empty_stage(self):
        enum, name = normalize_stage("")
        assert enum == ""
        assert name == ""


# ── 日期归一 ────────────────────────────────────────

class TestNormalizeDate:
    def test_iso_format(self):
        date, warn = normalize_date("2018-07-15")
        assert date == "2018-07-15"
        assert warn is None

    def test_slash_format(self):
        date, warn = normalize_date("2018/07/15")
        assert date == "2018-07-15"

    def test_dot_format(self):
        date, warn = normalize_date("2018.07.15")
        assert date == "2018-07-15"

    def test_invalid_date(self):
        date, warn = normalize_date("not a date")
        assert date is None
        assert warn is not None

    def test_empty_date(self):
        date, warn = normalize_date("")
        assert date is None

    def test_with_tournament_range_valid(self):
        """日期在赛事范围内，应通过"""
        date, warn = normalize_date("2018-07-15", "2018-06-14", "2018-07-15")
        assert date == "2018-07-15"
        assert warn is None

    def test_with_tournament_range_out_of_bounds(self):
        """日期超出赛事范围，应产生警告"""
        date, warn = normalize_date("2018-01-15", "2018-06-14", "2018-07-15")
        assert date == "2018-01-15"
        assert warn is not None
        assert "超出赛事范围" in warn


# ── 结果类型判断 ────────────────────────────────────

class TestDetermineResultType:
    def test_regulation(self):
        record = {"home_score_90": 4, "away_score_90": 2}
        assert determine_result_type(record) == "regulation"

    def test_draw(self):
        record = {"home_score_90": 1, "away_score_90": 1}
        assert determine_result_type(record) == "draw"

    def test_extra_time(self):
        record = {
            "home_score_90": 1, "away_score_90": 1,
            "home_score_et": 2, "away_score_et": 1,
        }
        assert determine_result_type(record) == "extra_time"

    def test_penalties(self):
        record = {
            "home_score_90": 3, "away_score_90": 3,
            "home_penalties": 4, "away_penalties": 2,
        }
        assert determine_result_type(record) == "penalties"

    def test_extra_time_by_flag(self):
        """仅靠 extra_time_flag 标记判断加时"""
        record = {
            "home_score_90": 2, "away_score_90": 1,
            "extra_time_flag": "1",
        }
        assert determine_result_type(record) == "extra_time"


# ── 比分显示 ────────────────────────────────────────

class TestGenerateScoreDisplay:
    def test_regulation_display(self):
        """v2: 返回 (score_display, penalty_score) 元组"""
        record = {"home_score_90": 4, "away_score_90": 2}
        score, pen = generate_score_display(record, "regulation")
        assert score == "4:2"
        assert pen == ""

    def test_extra_time_display(self):
        record = {
            "home_score_90": 1, "away_score_90": 1,
            "home_score_et": 2, "away_score_et": 1,
        }
        score, pen = generate_score_display(record, "extra_time")
        assert score == "2:1"
        assert pen == ""

    def test_penalties_display(self):
        record = {
            "home_score_90": 3, "away_score_90": 3,
            "home_penalties": 4, "away_penalties": 2,
        }
        score, pen = generate_score_display(record, "penalties")
        assert score == "3:3"
        assert pen == "4:2"

    def test_draw_display(self):
        record = {"home_score_90": 1, "away_score_90": 1}
        score, pen = generate_score_display(record, "draw")
        assert score == "1:1"
        assert pen == ""


# ── 比分校验 ────────────────────────────────────────

class TestValidateScoreConsistency:
    def test_regulation_valid(self):
        record = {"home_score_90": 4, "away_score_90": 2}
        errors = validate_score_consistency(record, "regulation", "team_A")
        assert len(errors) == 0

    def test_regulation_no_winner(self):
        record = {"home_score_90": 4, "away_score_90": 2}
        errors = validate_score_consistency(record, "regulation", None)
        assert len(errors) > 0

    def test_draw_has_winner(self):
        record = {"home_score_90": 1, "away_score_90": 1}
        errors = validate_score_consistency(record, "draw", "team_A")
        assert len(errors) > 0

    def test_penalties_missing_penalty_score(self):
        """点球大战但点球比分为空"""
        record = {"home_score_90": 3, "away_score_90": 3}
        errors = validate_score_consistency(record, "penalties", "team_A")
        assert len(errors) > 0


# ── 完整清洗流程 ────────────────────────────────────

class TestCleanMatchRecord:
    @pytest.fixture(autouse=True)
    def setup(self):
        alias_file = Path(__file__).parent.parent / "data" / "team_aliases.json"
        self.alias_data = load_team_aliases(str(alias_file))

    def test_clean_valid_record(self):
        record = {
            "match_date": "2018-07-15",
            "stage": "决赛",
            "home_team": "法国",
            "away_team": "克罗地亚",
            "home_score_90": 4,
            "away_score_90": 2,
        }
        cleaned, report = clean_match_record(record, self.alias_data)
        assert cleaned is not None
        assert cleaned["home_team_id"] == "team_FRA"
        assert cleaned["away_team_id"] == "team_CRO"
        assert cleaned["result_type"] == "regulation"
        assert cleaned["score_display"] == "4:2"
        assert cleaned["stage"] == "final"            # v2: 英文 enum
        assert cleaned["stage_name"] == "决赛"         # v2: 中文显示名
        assert cleaned["penalty_score"] == ""          # v2: penalty_score 独立字段
        assert report.valid == 1

    def test_clean_unknown_team(self):
        record = {
            "match_date": "2018-07-15",
            "stage": "决赛",
            "home_team": "火星队",
            "away_team": "克罗地亚",
            "home_score_90": 4,
            "away_score_90": 2,
        }
        cleaned, report = clean_match_record(record, self.alias_data)
        assert cleaned is None
        assert report.rejected == 1

    def test_clean_with_source_ids(self):
        """v2: source_ids 参数改为列表"""
        record = {
            "match_date": "2022-12-18",
            "stage": "决赛",
            "home_team": "阿根廷",
            "away_team": "法国",
            "home_score_90": 3,
            "away_score_90": 3,
            "home_penalties": 4,
            "away_penalties": 2,
        }
        cleaned, report = clean_match_record(
            record, self.alias_data,
            source_ids=["src_kaggle_001", "src_fifa_001"],
        )
        assert cleaned is not None
        assert "src_kaggle_001" in cleaned["source_ids"]
        assert "src_fifa_001" in cleaned["source_ids"]

    def test_same_team_rejected(self):
        """v2: 主客队相同应拒绝"""
        record = {
            "match_date": "2018-07-15",
            "stage": "决赛",
            "home_team": "法国",
            "away_team": "法国",
            "home_score_90": 4,
            "away_score_90": 2,
        }
        cleaned, report = clean_match_record(record, self.alias_data)
        assert cleaned is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
