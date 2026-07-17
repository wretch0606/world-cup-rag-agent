# C 成员 — 数据工程模块

> 世界杯知识库 — 数据底座 | v2.0 | 2026-07-16

## 📦 模块概览

本模块是整个系统的**数据底座**，负责原始数据采集、清洗、球队归一、比分口径校验、结构化存储和标准化事实文本生成。

```
原始数据（CSV/JSON）
  → 读取 & 校验 → 清洗 & 归一 → SQLite 入库 → match_facts.jsonl → 交付 D（Chroma）
```

## 📂 目录结构

```
C-data-pipeline/
├── data/                           ← 数据文件（给 B、D 消费）
│   ├── schema.sql                  ← 10 张表的完整建表 DDL
│   ├── team_aliases.json           ← 85 支球队中英别名（B、D 共用）
│   ├── tournaments.json            ← 22 届世界杯元数据
│   ├── stage_mapping.json          ← 阶段英文 enum ↔ 中文显示名
│   ├── source_manifest.json        ← 数据来源清单（4 个来源）
│   ├── match_facts.jsonl           ← ⭐ C→D 核心交付：964 条 Chroma 格式事实
│   ├── match_facts.json            ← 同上（美化 JSON，人工查阅用）
│   ├── cleaning_report.json        ← 清洗质量报告
│   ├── score_fix_report.json       ← 比分修正详情（73 场中 61 场自动修正）
│   ├── validation_report.json      ← 数据校验详细报告
│   └── validation_report.md        ← 数据校验摘要
├── src/                            ← Python 源码
│   ├── models/entities.py          ← 10 个数据实体 dataclass
│   ├── services/
│   │   ├── data_importer.py        ← CSV/JSON 读取与字段映射
│   │   ├── data_cleaner.py         ← 队名归一 / 日期校验 / 比分清洗
│   │   ├── fact_generator.py       ← 事实文本 + match_facts.jsonl 生成
│   │   └── db_schema.py            ← SQLite 建表 / CRUD / 批量操作
│   └── requirements.txt            ← Python 依赖
├── scripts/                        ← 可执行脚本
│   ├── import_data_v2.py           ← ⭐ 一键导入（原始→清洗→入库→事实文本）
│   ├── validate_data_v2.py         ← ⭐ 数据校验（对齐 P0 14 项验收）
│   ├── build_goals_team_map.py     ← 进球 team_id 映射构建
│   ├── fix_match_scores.py         ← 加时/点球比分自动修正
│   ├── update_score_display.py     ← score_display 字段更新
│   ├── detect_score_issues.py      ← 比分问题检测
│   ├── import_data.py              ← v1 导入（已弃用，保留兼容）
│   ├── validate_data.py            ← v1 校验（已弃用）
│   ├── build_aliases.py            ← 球队别名表构建
│   └── data_summary.py             ← 数据统计摘要
├── tests/                          ← 单元测试
│   ├── test_data_importer.py
│   ├── test_data_cleaner.py
│   └── test_fact_generator.py
├── raw_data/
│   └── matches_2022_sample.json    ← 样例数据（6 场 2022 世界杯）
└── docs/                           ← 文档
    ├── README.md                   ← 本文档
    ├── 数据字典.md                  ← 11 张表的完整字段说明
    ├── 数据总结.md                  ← 数据概览与统计
    ├── 世界杯比分.md                ← 2026 世界杯淘汰赛战报
    ├── VERSION.md                  ← 版本说明 / 变更摘要 / 重建方法
    ├── C成员开发指导文档.md         ← C 成员开发指导
    ├── 00-总体架构与数据流.md        ← 项目总架构
    ├── 01-C-to-D-Chroma入库接口契约.md   ← C→D 契约 v2.0
    ├── 02-D-to-E-检索结果接口契约.md     ← D→E 契约
    └── 03-E-to-B-RAG生成结果接口契约.md  ← E→B 契约
```

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r src/requirements.txt

# 2. 一键导入（需要 Kaggle CSV 在 raw_data/ 目录下）
python scripts/import_data_v2.py \
  --input "raw_data/FIFA World Cup 1930-2022 All Match Dataset.csv" \
  --source_type csv

# 3. 导入进球并修正比分
python scripts/build_goals_team_map.py
python scripts/fix_match_scores.py
python scripts/update_score_display.py

# 4. 运行校验
python scripts/validate_data_v2.py

# 5. 运行测试
cd tests
python -m pytest . -v
```

## 📊 数据规模

| 指标 | 数值 |
|------|------|
| 时间跨度 | 1930 — 2022（共 22 届） |
| 比赛总数 | 964 场 |
| 球队总数 | 85 支（含 9 支历史球队） |
| 进球事件 | 2,720 条（覆盖 886 场比赛） |
| 数据来源 | 4 个公开来源（Kaggle / FIFA / Wikipedia） |

## 🔑 给各组员的接口说明

### 给 B（FastAPI / LangGraph）

| 你需要知道的 | 详情 |
|------|------|
| 数据库 | `data/worldcup_v2.db`（通过脚本重建，不直接入库） |
| `stage` 列 | 英文 enum（`final`），中文用 `stage_name` |
| `penalty_score` | **独立字段**（`"4:2"`），不要从 `score_display` 拆 |
| 精确事实 | 比分/日期/胜者直接走 SQLite，不调 RAG |
| 最终响应 | `intent`、`graph`、`trace_id` 由 B 生成；E 只给 `answer/facts/sources` |

关键 SQL 示例：

```sql
-- 按球队查比赛
SELECT * FROM matches WHERE home_team_id = 'team_ARG' OR away_team_id = 'team_ARG';

-- 按年份+阶段查
SELECT * FROM matches WHERE tournament_year = 2022 AND stage = 'final';

-- 查某场比赛的全部来源
SELECT s.* FROM sources s
JOIN match_sources ms ON s.source_id = ms.source_id
WHERE ms.match_id = 'M-2022-64';
```

### 给 D（Chroma 检索）

| 你需要知道的 | 详情 |
|------|------|
| 入库文件 | `data/match_facts.jsonl`（每行一个 JSON，964 条） |
| 幂等 key | `id` 字段（`match_fact_M-2022-64_v2`），执行 upsert |
| 过滤支持 | `years`、`team_ids`、`stages`、`result_types`、`match_ids` |
| 透传字段 | `source_id`、`source_url`、`source_page`、`data_version` 原样回到 E |
| 不生成答案 | D 只返回 candidates + 评分，答案由 E 生成 |

`match_facts.jsonl` 格式：

```json
{
  "id": "match_fact_M-2022-64_v2",
  "text": "2022年世界杯决赛，阿根廷队...",
  "metadata": {
    "match_id": "M-2022-64",
    "tournament_year": 2022,
    "stage": "决赛",
    "team_ids": ["team_ARG", "team_FRA"],
    "result_type": "penalties",
    "source_id": "src_csv_20260716_001",
    "document_name": "FIFA World Cup 2022",
    "source_url": "https://www.kaggle.com/datasets/...",
    "source_page": null,
    "chunk_index": 0,
    "language": "zh",
    "data_version": "2026-07-16-v2"
  }
}
```

若 Chroma 版本不支持数组类型 `team_ids`，序列化为 `"team_ARG,team_FRA"`。

### 给 E（RAG 生成与评测）

| 你需要知道的 | 详情 |
|------|------|
| 精确事实不经过你 | 比分/日期/胜者由 B 从 SQLite 直接返回 |
| 不碰数据库 | 结构化事实由 B 通过 `RAGRequest.structured_facts` 传入 |
| 冲突处理 | D 的文本证据与 B 的 SQL 事实冲突时，以 SQL 为准，产生 `SOURCE_CONFLICT` 告警 |
| 不生成的内容 | `graph`、`intent`、`trace_id` 由 B 组装 |
| 数据质量 | 见 `validation_report.md`（已知限制） |

关键字段：
- `score_display`：正式比分（如 `"3:3"`）
- `penalty_score`：点球比分（如 `"4:2"`），独立字段
- `stage`：英文枚举（`final`），中文显示名用 `stage_name`
- `source_ids`：数组，从 `StructuredFact` 和 `EvidenceItem` 中收集

### 给 A（前端）

A 只通过 B 的 API 获取数据，不直接读取本模块文件。需要了解的字段语义见 `数据字典.md`。

## 📋 比分口径

| 类型 | 判定条件 | 示例 |
|------|---------|------|
| `regulation` | 90 分钟分出胜负 | `4:2` |
| `extra_time` | 加时赛后分出胜负 | `2:1`（加时结束累计） |
| `penalties` | 点球大战决出晋级 | `score_display="3:3"`, `penalty_score="4:2"` |
| `draw` | 90 分钟平局 | `1:1` |

## ⚠️ 已知限制

1. 12 场加时/点球比赛缺少进球数据，90 分钟比分未自动修正（清单见 `data/score_fix_report.json`）
2. 点球大战逐轮数据缺失（goals 中无 `match_period='penalties'` 记录）
3. 数据来源于 Kaggle 公开数据集，未与 FIFA 官方记录逐场交叉校验
4. `world_cup_reports` collection 的 PDF/网页文本未导入

## 🔄 数据重建

在新环境中重建 v2 数据库，按「快速开始」中的步骤执行即可。数据库文件 `worldcup_v2.db` 不入 Git 仓库（`.gitignore` 已排除），通过脚本从原始 CSV 重新生成。

## 📝 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v1.0 | 2026-07-15 | 初始版本：4 张表，964 场比赛 |
| v2.0 | 2026-07-16 | 比分口径修正、Schema 升级至 10 张表、英文阶段枚举、match_facts.jsonl 对齐 RAG 契约 |

详见 [VERSION.md](./VERSION.md)。
