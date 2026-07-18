"""
数据导入器测试
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.data_importer import (
    import_csv, import_json, validate_raw_record,
    compute_checksum, generate_source_id, get_file_type,
)


class TestGetFileType:
    def test_csv(self):
        assert get_file_type("data.csv") == "csv"
    def test_json(self):
        assert get_file_type("data.JSON") == "json"
    def test_pdf(self):
        assert get_file_type("报告.PDF") == "pdf"


class TestValidateRawRecord:
    def test_all_fields_present(self):
        record = {
            "match_date": "2018-07-15", "stage": "决赛",
            "home_team": "法国", "away_team": "克罗地亚",
            "home_score_90": "4", "away_score_90": "2",
        }
        missing = validate_raw_record(record)
        assert missing == []

    def test_missing_fields(self):
        record = {"match_date": "2018-07-15"}
        missing = validate_raw_record(record)
        assert "stage" in missing
        assert "home_team" in missing


class TestImportCsv:
    def test_basic_csv(self):
        csv_content = "match_date,stage,home_team,away_team,home_score_90,away_score_90\n"
        csv_content += "2018-07-15,决赛,法国,克罗地亚,4,2\n"
        csv_content += "2018-07-14,三四名决赛,比利时,英格兰,2,0\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        ) as f:
            f.write(csv_content)
            path = f.name
        try:
            records = import_csv(path)
            assert len(records) == 2
            assert records[0]["home_team"] == "法国"
            assert records[0]["home_score_90"] == "4"
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            import_csv("不存在的文件.csv")


class TestImportJson:
    def test_basic_json_array(self):
        data = [
            {"match_date": "2018-07-15", "stage": "决赛",
             "home_team": "法国", "away_team": "克罗地亚",
             "home_score_90": 4, "away_score_90": 2},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            records = import_json(path)
            assert len(records) == 1
            assert records[0]["home_team"] == "法国"
        finally:
            os.unlink(path)

    def test_json_with_matches_key(self):
        data = {"matches": [
            {"match_date": "2018-07-15", "home_team": "法国", "away_team": "克罗地亚",
             "home_score_90": 4, "away_score_90": 2, "stage": "决赛"},
        ]}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            records = import_json(path)
            assert len(records) == 1
        finally:
            os.unlink(path)


class TestGenerateSourceId:
    def test_format(self):
        sid = generate_source_id("csv", "matches_2018", 1)
        assert sid.startswith("src_csv_")
        assert sid.endswith("_001")


class TestComputeChecksum:
    def test_checksum(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("hello world")
            path = f.name
        try:
            cs = compute_checksum(path)
            assert len(cs) == 32  # MD5 hex length
        finally:
            os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
