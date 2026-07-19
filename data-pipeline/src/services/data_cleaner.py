"""
数据清洗器 v2

改进点（对齐整改清单和 RAG 接口契约）：
1. 阶段归一为英文枚举（final/group…），中文显示名存入 stage_name
2. 日期解析使用 tournament 范围校验，禁止自动猜测 DD/MM vs MM/DD
3. 保留 raw_match_date 原始值
4. penalty_score 独立于 score_display
5. 输出 StructuredFact 格式
"""

import json
import re
from pathlib import Path
from datetime import datetime, date
from typing import Optional

from models.entities import CleaningReport


# ═══════════════════════════════════════════════════════════
#  别名映射加载
# ═══════════════════════════════════════════════════════════

def load_team_aliases(mapping_file: str) -> dict:
    """
    加载球队别名映射文件。

    返回:
        {
            "alias_map": {别名 → team_id},
            "team_info": {team_id → {canonical_name, confederation, ...}},
        }
    """
    path = Path(mapping_file)
    if not path.exists():
        raise FileNotFoundError(f"别名映射文件不存在: {mapping_file}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "alias_map": data.get("aliases", {}),
        "team_info": data.get("teams", {}),
    }


# ═══════════════════════════════════════════════════════════
#  阶段映射加载（英文 enum ↔ 中文显示名）
# ═══════════════════════════════════════════════════════════

_stage_data = None


def _load_stage_mapping() -> dict:
    """加载阶段映射文件（惰性加载）。"""
    global _stage_data
    if _stage_data is not None:
        return _stage_data
    # 从 src/services/ 向上两级到项目根目录 (-RAG-/)
    path = Path(__file__).parent.parent.parent / "data" / "stage_mapping.json"
    with open(path, "r", encoding="utf-8") as f:
        _stage_data = json.load(f)
    return _stage_data


def normalize_stage(raw_stage: str) -> tuple[str, str]:
    """
    将原始阶段名转为英文 enum + 中文显示名。

    返回: (enum_value, stage_name)
      例: "final" → ("final", "决赛")
          "round of 16" → ("round_of_16", "1/8决赛")
          无法识别 → (raw, raw)
    """
    if not raw_stage:
        return "", ""

    mapping = _load_stage_mapping()
    display_to_enum = mapping.get("display_to_enum", {})
    enum_to_display = mapping.get("enum_to_display", {})

    name = raw_stage.strip()

    # 1. 直接匹配英文枚举
    if name in enum_to_display:
        return name, enum_to_display[name]

    # 2. 从 display_to_enum 查找
    key_lower = name.lower()
    if key_lower in display_to_enum:
        enum_val = display_to_enum[key_lower]
        return enum_val, enum_to_display.get(enum_val, name)

    # 3. 中文直接匹配
    if name in display_to_enum:
        enum_val = display_to_enum[name]
        return enum_val, enum_to_display.get(enum_val, name)

    # 无法识别，返回原值
    return name, name


def stage_enum_to_display(enum_val: str) -> str:
    """英文枚举 → 中文显示名"""
    mapping = _load_stage_mapping()
    return mapping.get("enum_to_display", {}).get(enum_val, enum_val)


# ═══════════════════════════════════════════════════════════
#  队名归一
# ═══════════════════════════════════════════════════════════

def normalize_team_name(raw_name: str, alias_map: dict) -> tuple[Optional[str], Optional[str]]:
    """
    将原始队名映射到规范 team_id。

    匹配优先级：
    1. 精确匹配 alias_map
    2. 大小写不敏感匹配
    3. 模糊匹配（包含关系）

    返回: (team_id, 匹配方式)
    """
    if not raw_name or not isinstance(raw_name, str):
        return None, None

    name = raw_name.strip()

    if name in alias_map:
        return alias_map[name], None

    name_lower = name.lower()
    for alias, team_id in alias_map.items():
        if alias.lower() == name_lower:
            return team_id, f"case_insensitive:{alias}→{team_id}"

    for alias, team_id in alias_map.items():
        if name_lower in alias.lower() or alias.lower() in name_lower:
            return team_id, f"fuzzy:{name}→{team_id}"

    return None, None


# ═══════════════════════════════════════════════════════════
#  日期归一（含 tournament 范围校验）
# ═══════════════════════════════════════════════════════════

def normalize_date(
    raw_date: str,
    tournament_start: Optional[str] = None,
    tournament_end: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    统一日期格式为 YYYY-MM-DD。

    支持的输入格式：
    - "2018-07-15", "2018/07/15"
    - "7/15/2018" (Kaggle 默认: MM/DD/YYYY)
    - "15 July 2018", "July 15, 2018"

    如果提供了 tournament 日期范围，会进行校验。
    无法确定时为明确格式写死，不自动猜测。

    返回: (归一化日期, 警告信息)
    """
    if not raw_date:
        return None, "日期为空"

    date_str = str(raw_date).strip()

    # 按优先级尝试：明确的 ISO 格式优先，斜杠格式其次（Kaggle），横杠格式最后（歧义风险）
    # 注意：%d-%m-%Y 和 %m-%d-%Y 对 day≤12 的日期存在歧义，
    # 如 04-05-2018 无法区分 MM-DD 还是 DD-MM，依靠 tournament 范围校验兜底
    priority_formats = [
        "%Y-%m-%d",     # ISO 8601: 2018-07-15（无歧义）
        "%Y/%m/%d",     # 2018/07/15（无歧义）
        "%Y.%m.%d",     # 2018.07.15（无歧义）
        "%m/%d/%Y",     # 7/15/2018 (Kaggle 数据集标准格式，斜杠无歧义)
        "%Y%m%d",       # 20180715
        "%d %B %Y",     # 15 July 2018（月份英文，无歧义）
        "%B %d, %Y",    # July 15, 2018
        "%d %b %Y",     # 15 Jul 2018
        "%b %d, %Y",    # Jul 15, 2018
        "%d-%m-%Y",     # 15-07-2018（⚠️ 最低优先级：与 MM-DD-YYYY 歧义，依赖范围校验）
    ]

    parsed = None
    matched_fmt = None
    for fmt in priority_formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            matched_fmt = fmt
            break
        except ValueError:
            continue

    if parsed is None:
        return None, f"无法解析日期: {raw_date}"

    normalized = parsed.strftime("%Y-%m-%d")

    # 如果有 tournament 日期范围，进行校验
    if tournament_start and tournament_end:
        try:
            start_dt = datetime.strptime(tournament_start, "%Y-%m-%d")
            end_dt = datetime.strptime(tournament_end, "%Y-%m-%d")
            if parsed < start_dt or parsed > end_dt:
                return normalized, (
                    f"日期 {normalized} 超出赛事范围 "
                    f"[{tournament_start}, {tournament_end}]，"
                    f"解析格式: {matched_fmt}"
                )
        except ValueError:
            pass  # tournament 日期格式异常，跳过校验

    # 对于 DD/MM vs MM/DD 歧义格式做额外检查
    if matched_fmt == "%m/%d/%Y":
        # Kaggle 标准格式，可信但标记为低置信度
        return normalized, None

    return normalized, None


# ═══════════════════════════════════════════════════════════
#  比分口径判断
# ═══════════════════════════════════════════════════════════

def determine_result_type(record: dict) -> str:
    """
    根据比分字段判断比赛结果类型。

    判断逻辑（优先级从高到低）：
    1. 有点球数据 → "penalties"
    2. 有 extra_time_flag 标记且加时比分≠90分钟比分 → "extra_time"
    3. 90分钟比分不等 → "regulation"
    4. 90分钟比分相等 → "draw"
    """
    home_pen = record.get("home_penalties")
    away_pen = record.get("away_penalties")

    if (home_pen is not None and home_pen != "" and home_pen != 0) or \
       (away_pen is not None and away_pen != "" and away_pen != 0):
        return "penalties"

    home_et = record.get("home_score_et")
    away_et = record.get("away_score_et")
    home_90 = _to_int(record.get("home_score_90"))
    away_90 = _to_int(record.get("away_score_90"))

    is_et_flag = str(record.get("extra_time_flag", "")).strip() == "1"
    if is_et_flag:
        return "extra_time"
    if home_et is not None and home_et != "" and away_et is not None and away_et != "":
        h_et = _to_int(home_et)
        a_et = _to_int(away_et)
        if h_et != home_90 or a_et != away_90:
            return "extra_time"

    if home_90 != away_90:
        return "regulation"

    return "draw"


def generate_score_display(record: dict, result_type: str) -> tuple[str, str]:
    """
    根据结果类型生成比分显示字符串。

    返回: (score_display, penalty_score)
    - regulation:  ("4:2", "")
    - extra_time:  ("2:1", "")
    - penalties:   ("3:3", "4:2")
    - draw:        ("1:1", "")
    """
    home_90 = _to_int(record.get("home_score_90", 0))
    away_90 = _to_int(record.get("away_score_90", 0))

    if result_type == "regulation":
        return f"{home_90}:{away_90}", ""

    elif result_type == "extra_time":
        h_et = _to_int(record.get("home_score_et") or home_90)
        a_et = _to_int(record.get("away_score_et") or away_90)
        return f"{h_et}:{a_et}", ""

    elif result_type == "penalties":
        h_pen = _to_int(record.get("home_penalties") or 0)
        a_pen = _to_int(record.get("away_penalties") or 0)
        pen_score = f"{h_pen}:{a_pen}"
        h_et = _to_int(record.get("home_score_et") or home_90)
        a_et = _to_int(record.get("away_score_et") or away_90)
        if h_et != home_90 or a_et != away_90:
            return f"{h_et}:{a_et}", pen_score
        return f"{home_90}:{away_90}", pen_score

    else:  # draw
        return f"{home_90}:{away_90}", ""


def validate_score_consistency(record: dict, result_type: str,
                                winner_team_id: Optional[str]) -> list[str]:
    """
    交叉校验比分逻辑一致性。

    检查项：
    1. regulation / extra_time 必须有胜者且比分不相等
    2. draw 不能有胜者，且 90 分钟比分必须相等
    3. penalties 的正式比分（90分钟或加时结束）必须相等
    4. penalties 必须有点球比分
    """
    errors = []

    home_90 = _to_int(record.get("home_score_90", 0))
    away_90 = _to_int(record.get("away_score_90", 0))

    if result_type == "regulation":
        if home_90 == away_90:
            errors.append(f"result_type=regulation 但 90 分钟比分为平局 {home_90}:{away_90}")
        if not winner_team_id:
            errors.append("result_type=regulation 但 winner_team_id 为空")

    elif result_type == "extra_time":
        has_et_flag = str(record.get("extra_time_flag", "")).strip() == "1"
        if not has_et_flag:
            if home_90 != away_90:
                errors.append(f"result_type=extra_time 但 90 分钟比分已分出胜负 {home_90}:{away_90}")
        h_final = _to_int(record.get("home_score_et") or home_90)
        a_final = _to_int(record.get("away_score_et") or away_90)
        if not winner_team_id and h_final != a_final:
            errors.append("result_type=extra_time 但 winner_team_id 为空且比分不等")

    elif result_type == "draw":
        if home_90 != away_90:
            errors.append(f"result_type=draw 但 90 分钟比分不相等 {home_90}:{away_90}")
        if winner_team_id:
            errors.append(f"result_type=draw 但 winner_team_id 不为空: {winner_team_id}")

    elif result_type == "penalties":
        h_et = _to_int(record.get("home_score_et") or home_90)
        a_et = _to_int(record.get("away_score_et") or away_90)
        if h_et != a_et:
            errors.append(f"result_type=penalties 但加时结束比分不相等 {h_et}:{a_et}")
        h_pen = record.get("home_penalties")
        a_pen = record.get("away_penalties")
        if (h_pen is None or h_pen == "" or h_pen == 0) and \
           (a_pen is None or a_pen == "" or a_pen == 0):
            errors.append("result_type=penalties 但点球比分为空或0")

    return errors


# ═══════════════════════════════════════════════════════════
#  Tournament 数据加载
# ═══════════════════════════════════════════════════════════

_tournament_data = None


def load_tournament_data() -> dict:
    """加载 22 届世界杯 tournament 数据。"""
    global _tournament_data
    if _tournament_data is not None:
        return _tournament_data
    # 从 src/services/ 向上两级到项目根目录 (-RAG-/)
    path = Path(__file__).parent.parent.parent / "data" / "tournaments.json"
    with open(path, "r", encoding="utf-8") as f:
        _tournament_data = json.load(f)
    return _tournament_data


def get_tournament_by_year(year: int) -> Optional[dict]:
    """根据年份获取 tournament 信息。"""
    data = load_tournament_data()
    for t in data.get("tournaments", {}).values():
        if t["year"] == year:
            return t
    return None


# ═══════════════════════════════════════════════════════════
#  单条记录清洗（主函数）
# ═══════════════════════════════════════════════════════════

def clean_match_record(
    record: dict,
    alias_data: dict,
    source_ids: Optional[list] = None,
    data_version: str = "2026-07-16-v2",
) -> tuple[Optional[dict], CleaningReport]:
    """
    清洗单条原始比赛记录。

    参数:
        record:       CSV/JSON 读出的原始字典
        alias_data:   load_team_aliases() 的返回值
        source_ids:   数据来源 ID 列表
        data_version: 数据版本号

    返回: (清洗后的 dict 或 None(无法修复), 单条记录的 CleaningReport)

    清洗步骤：
    1. normalize_team_name() → team_id
    2. normalize_date() + tournament 范围校验
    3. normalize_stage() → (英文enum, 中文显示名)
    4. determine_result_type()
    5. generate_score_display() → (正式比分, 点球比分)
    6. determine_winner()
    7. validate_score_consistency()
    """
    if source_ids is None:
        source_ids = []
    report = CleaningReport(total_records=1)

    # ── 1. 球队名归一 ──
    home_raw = record.get("home_team", "")
    away_raw = record.get("away_team", "")
    alias_map = alias_data["alias_map"]

    home_id, home_warn = normalize_team_name(home_raw, alias_map)
    away_id, away_warn = normalize_team_name(away_raw, alias_map)

    if not home_id:
        report.add_error(
            record.get("match_id", "unknown"),
            f"无法识别主队名称: {home_raw}",
            field="home_team", value=str(home_raw),
        )
        return None, report
    if not away_id:
        report.add_error(
            record.get("match_id", "unknown"),
            f"无法识别客队名称: {away_raw}",
            field="away_team", value=str(away_raw),
        )
        return None, report

    if home_id == away_id:
        report.add_error(
            record.get("match_id", "unknown"),
            f"主客队相同: {home_id}",
            field="home_team", value=str(home_raw),
        )
        return None, report

    if home_warn:
        report.add_warning(record.get("match_id", "unknown"),
                           "home_team", str(home_raw), home_warn)
    if away_warn:
        report.add_warning(record.get("match_id", "unknown"),
                           "away_team", str(away_raw), away_warn)

    # ── 2. 确定年份和 tournament ──
    year_raw = record.get("tournament_year")
    # 优先从日期提取年份
    date_raw = record.get("match_date", "")

    # 先解析日期以确定年份（前提是日期格式可靠）
    # 先用宽松解析提取年份
    year = _extract_year_from_any(date_raw, year_raw)
    tournament = get_tournament_by_year(year) if year else None

    # ── 3. 日期归一（含 tournament 范围校验）──
    date_norm, date_warn = normalize_date(
        date_raw,
        tournament_start=tournament["start_date"] if tournament else None,
        tournament_end=tournament["end_date"] if tournament else None,
    )
    if not date_norm:
        report.add_error(record.get("match_id", "unknown"),
                         date_warn or "日期解析失败",
                         field="match_date", value=str(date_raw))
        return None, report
    if date_warn:
        report.add_warning(record.get("match_id", "unknown"),
                           "match_date", str(date_raw), date_warn)

    # ── 4. 阶段归一 → 英文 enum + 中文名 ──
    stage_raw = record.get("stage", "")
    stage_enum, stage_name = normalize_stage(stage_raw)
    if stage_enum != stage_raw:
        report.add_warning(record.get("match_id", "unknown"),
                           "stage", str(stage_raw),
                           f"normalized:{stage_raw}→{stage_enum}")

    # ── 5. 比分转为整数 ──
    home_90 = _to_int(record.get("home_score_90", 0))
    away_90 = _to_int(record.get("away_score_90", 0))
    home_et = _to_int_or_none(record.get("home_score_et"))
    away_et = _to_int_or_none(record.get("away_score_et"))
    home_pen = _to_int_or_none(record.get("home_penalties"))
    away_pen = _to_int_or_none(record.get("away_penalties"))

    # ── 6. 结果类型判断 ──
    temp = {**record, "home_score_90": home_90, "away_score_90": away_90,
            "home_score_et": home_et, "away_score_et": away_et,
            "home_penalties": home_pen, "away_penalties": away_pen}
    result_type = determine_result_type(temp)

    # ── 7. 生成显示比分 ──
    score_display, penalty_score = generate_score_display(temp, result_type)

    # ── 8. 确定胜者 ──
    winner_id = _determine_winner(temp, result_type, home_id, away_id)

    # ── 9. 生成 match_id ──
    match_id = record.get("match_id", "") or _generate_match_id(
        date_norm, home_id, away_id, year or 0,
    )

    # ── 10. 交叉校验 ──
    score_errors = validate_score_consistency(temp, result_type, winner_id)
    for err in score_errors:
        report.add_error(match_id, err)

    if score_errors:
        return None, report

    # ── 11. 组装清洗后记录 ──
    cleaned = {
        "match_id":        match_id,
        "tournament_id":   tournament["tournament_id"] if tournament else (f"WC-{year}" if year else "WC-UNKNOWN"),
        "tournament_year": year or _extract_year(date_norm, 0),
        "match_date":      date_norm,
        "raw_match_date":  str(date_raw),
        "stage":           stage_enum,
        "stage_name":      stage_name,
        "group_name":      record.get("group_name", ""),
        "venue":           record.get("venue", ""),
        "city":            record.get("city", ""),
        "home_team_id":    home_id,
        "away_team_id":    away_id,
        "home_score_90":   home_90,
        "away_score_90":   away_90,
        "home_score_et":   home_et,
        "away_score_et":   away_et,
        "home_penalties":  home_pen,
        "away_penalties":  away_pen,
        "winner_team_id":  winner_id,
        "result_type":     result_type,
        "score_display":   score_display,
        "penalty_score":   penalty_score,
        "source_ids":      source_ids or [record.get("source_id", "")],
        "data_version":    data_version or record.get("data_version", "2026-07-16-v2"),
    }

    report.valid = 1
    return cleaned, report


# ═══════════════════════════════════════════════════════════
#  goals.team_id 映射
# ═══════════════════════════════════════════════════════════

def map_goals_team_id(goals_team_id: str, team_name: str,
                       alias_map: dict) -> tuple[str, str]:
    """
    将 goals 表中的旧 team_id (如 "T-28") 映射为新的规范 team_id (如 "team_FRA")。

    策略：优先使用 team_name 匹配，其次使用旧 team_id 的数字部分映射。

    返回: (new_team_id, source_team_id)
    """
    source_team_id = goals_team_id

    # 1. 通过 team_name 匹配
    if team_name:
        new_id, _ = normalize_team_name(team_name, alias_map)
        if new_id:
            return new_id, source_team_id

    # 2. 如果已经是规范格式，直接保留
    if goals_team_id.startswith("team_"):
        return goals_team_id, source_team_id

    # 3. 无法映射，保留旧 ID 作为 source_team_id，team_id 置空
    return "", source_team_id


# ═══════════════════════════════════════════════════════════
#  内部工具函数
# ═══════════════════════════════════════════════════════════

def _to_int(value) -> int:
    """安全转为 int，None/空/无效返回 0。"""
    if value is None or value == "" or value == "None":
        return 0
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return 0


def _to_int_or_none(value) -> Optional[int]:
    """安全转为 int，None/空返回 None。"""
    if value is None or value == "" or value == "None":
        return None
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def _determine_winner(record: dict, result_type: str,
                       home_id: str, away_id: str) -> Optional[str]:
    """根据比分确定胜者 team_id。"""
    if result_type == "draw":
        return None

    if result_type == "penalties":
        home_pen = _to_int(record.get("home_penalties") or 0)
        away_pen = _to_int(record.get("away_penalties") or 0)
        if home_pen > away_pen:
            return home_id
        if away_pen > home_pen:
            return away_id
        return None  # 点球比分相等时无法判定（不应出现）

    home_final = _to_int(record.get("home_score_et") or record.get("home_score_90", 0))
    away_final = _to_int(record.get("away_score_et") or record.get("away_score_90", 0))
    if home_final > away_final:
        return home_id
    elif away_final > home_final:
        return away_id
    return None


def _extract_year(date_str: str, fallback) -> int:
    """从日期字符串提取年份。"""
    try:
        return int(date_str[:4])
    except (ValueError, TypeError):
        try:
            return int(fallback)
        except (ValueError, TypeError):
            return 0


def _extract_year_from_any(date_str: str, fallback) -> Optional[int]:
    """从任意日期字符串提取年份（宽松解析）。"""
    if not date_str:
        try:
            return int(fallback) if fallback else None
        except (ValueError, TypeError):
            return None

    # 尝试 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    m = re.match(r'(\d{4})[-/.\s]', str(date_str).strip())
    if m:
        return int(m.group(1))

    # 尝试 MM/DD/YYYY / DD/MM/YYYY
    m = re.search(r'(\d{4})$', str(date_str).strip())
    if m:
        return int(m.group(1))

    try:
        return int(fallback) if fallback else None
    except (ValueError, TypeError):
        return None


def _generate_match_id(date_str: str, home_id: str, away_id: str,
                        year: int) -> str:
    """生成 match_id。格式: M-{year}-{序号}，按年份独立编号。"""
    return f"M-{year}-{_match_counter(year):03d}"


_match_counters: dict[int, int] = {}


def _match_counter(year: Optional[int] = None) -> int:
    """获取当前计数器并在原地加 1。批次导入前应调用 reset_match_counter()。"""
    global _match_counters
    key = year or 0
    _match_counters[key] = _match_counters.get(key, 0) + 1
    return _match_counters[key]


def reset_match_counter(year: Optional[int] = None) -> None:
    """重置 match ID 计数器。"""
    global _match_counters
    if year is not None:
        _match_counters.pop(year, None)
    else:
        _match_counters.clear()
