"""
数据导入器

支持 CSV、JSON 格式的赛事数据读取，以及 PDF 文本提取。
所有导入函数返回原始 dict 列表，不做清洗（清洗由 data_cleaner 负责）。
"""

import csv
import json
import hashlib
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════
#  CSV 导入
# ═══════════════════════════════════════════════════════════

def import_csv(file_path: str, encoding: str = "auto",
               field_map: Optional[dict] = None) -> list[dict]:
    """
    读取 CSV 赛事数据，返回字典列表。

    encoding="auto" 时自动检测 UTF-8 → GBK → Latin-1。
    若提供 field_map，会将 CSV 列名映射为内部字段名。
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if encoding == "auto":
        encodings = ["utf-8-sig", "utf-8", "gbk", "latin-1"]
    else:
        encodings = [encoding]

    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                records = []
                for row in reader:
                    if any(v.strip() for v in row.values() if v):
                        records.append(row)
                # 字段名映射（如 "Home Team Name" → "home_team"）
                if field_map:
                    records = [_apply_field_map(r, field_map) for r in records]
                return records
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(f"无法识别文件编码，已尝试: {encodings}")


def _apply_field_map(record: dict, field_map: dict) -> dict:
    """将 CSV 原始列名映射为内部字段名。只保留映射中存在的列。"""
    mapped = {}
    for csv_col, internal_col in field_map.items():
        if csv_col in record:
            mapped[internal_col] = record[csv_col]
    # 保留未映射的原始列（如 Win conditions 等附加字段）
    for col, val in record.items():
        if col not in field_map and col not in mapped:
            mapped[col] = val
    return mapped


# Kaggle 数据集预设映射（Jahaidul Islam: FIFA World Cup 1930-2022 All Match Dataset）
KAGGLE_MATCH_MAP = {
    "Match Date":         "match_date",
    "Match Time":         "match_time",
    "Stage Name":         "stage",
    "Group Name":         "group_name",
    "Stadium Name":       "venue",
    "City Name":          "city",
    "Country Name":       "host_country",
    "Home Team Name":     "home_team",
    "Away Team Name":     "away_team",
    "Home Team Score":    "home_score_90",
    "Away Team Score":    "away_score_90",
    "Home Team Score Penalties": "home_penalties",
    "Away Team Score Penalties": "away_penalties",
    "Extra Time":         "extra_time_flag",
    "Penalty Shootout":   "penalty_shootout_flag",
    "Match Id":           "match_id",
    "Tournament Id":      "tournament_id",
    "tournament Name":    "tournament_name",
    "Result":             "match_result",
    "Score":              "score_original",
}


# ═══════════════════════════════════════════════════════════
#  JSON 导入
# ═══════════════════════════════════════════════════════════

def import_json(file_path: str) -> list[dict]:
    """
    读取 JSON 赛事数据，返回字典列表。

    支持的 JSON 结构：
    - 顶层为数组：[{...}, {...}]
    - 顶层为对象且含 "matches"/"data"/"records" 键 → 自动提取该键的值
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 如果是 list，直接返回
    if isinstance(data, list):
        return data

    # 如果是 dict，尝试从常见的包装键中提取列表
    if isinstance(data, dict):
        for key in ("matches", "data", "records", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # 没有找到列表键，可能是单条记录，包装为列表
        return [data]

    raise ValueError(f"无法识别的 JSON 结构: {type(data)}")


# ═══════════════════════════════════════════════════════════
#  必填字段校验
# ═══════════════════════════════════════════════════════════

# 一条有效比赛记录必须具备的字段
MATCH_REQUIRED_FIELDS = [
    "match_date", "stage", "home_team", "away_team",
    "home_score_90", "away_score_90",
]


def validate_raw_record(record: dict) -> list[str]:
    """
    校验单条记录的必填字段。

    返回缺失字段名列表。空列表 = 校验通过。
    """
    missing = []
    for field in MATCH_REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


# ═══════════════════════════════════════════════════════════
#  PDF 文本提取
# ═══════════════════════════════════════════════════════════

def import_pdf_text(file_path: str) -> str:
    """
    提取 PDF 文件中的文本。

    策略：优先使用 pypdf 提取文字层；若为空，尝试 OCR 回退；
    若 MinerU API 可用则优先调用（需配置 MINERU_ENDPOINT 环境变量）。
    """
    import os

    # 优先尝试 MinerU（如果配置了端点）
    mineru_endpoint = os.environ.get("MINERU_ENDPOINT", "")
    if mineru_endpoint:
        result = _import_via_mineru(file_path, mineru_endpoint)
        if result:
            return result

    # pypdf 文字层提取
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
            except Exception:
                continue
        if pages:
            return "\n\n".join(pages)
    except ImportError:
        pass
    except Exception:
        pass

    # OCR 回退
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(file_path, dpi=200)
        pages = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages) if pages else ""
    except ImportError:
        return "[OCR 依赖未安装。请运行: pip install pytesseract pdf2image]"
    except Exception as e:
        return f"[PDF 解析失败: {e}]"


def _import_via_mineru(file_path: str, endpoint: str) -> str:
    """通过 MinerU API 解析 PDF。endpoint 格式如 http://localhost:8080/api/parse"""
    try:
        import requests
        with open(file_path, "rb") as f:
            resp = requests.post(
                endpoint,
                files={"file": f},
                timeout=120,
            )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("text", "") or data.get("content", "")
    except ImportError:
        pass
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════

def compute_checksum(file_path: str) -> str:
    """计算文件 MD5，用于 source 表校验。"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def generate_source_id(source_type: str, title: str, index: int = 1) -> str:
    """
    生成规范的 source_id。
    格式: src_{type}_{日期}_{序号}
    示例: src_csv_20250101_001
    """
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    short_title = title[:8].replace(" ", "_").lower()
    return f"src_{source_type}_{today}_{index:03d}"


def get_file_type(filename: str) -> str:
    """获取文件扩展名（小写，不含点）。"""
    return Path(filename).suffix.lower().lstrip(".")
