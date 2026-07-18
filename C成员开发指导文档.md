# 成员 C（数据工程）：世界杯知识库 — 开发指导文档

> **成员角色**：数据工程负责人  
> **核心任务**：赛事数据采集、清洗、球队归一、比分口径、事实文本生成  
> **交付物**：数据字典、清洗脚本、异常报告、结构化数据库、事实文本 JSON

---

## 一、模块定位

你是整个系统的**数据底座**——你的数据质量直接决定 RAG 回答的准确性。

```
原始数据（CSV/JSON/PDF）
  → [1] 读取 & 校验
  → [2] 球队别名归一
  → [3] 日期/阶段/比分清洗
  → [4] 结果类型判断（regulation/extra_time/penalties/draw）
  → [5] 写入 SQLite（4 张核心表）
  → [6] 生成事实文本 → 交给成员 D 写入 Chroma
```

---

## 二、已交付文件清单

```
小组作业/
├── backend/
│   ├── models/
│   │   └── entities.py              ← 数据实体 dataclass（Tournament/Team/Match/Source）
│   ├── services/
│   │   ├── data_importer.py         ← 数据导入：CSV/JSON/PDF
│   │   ├── data_cleaner.py          ← 数据清洗：队名/日期/阶段/比分
│   │   ├── fact_generator.py        ← 事实文本：比赛→中文叙述
│   │   └── db_schema.py             ← SQLite 操作：建表/CRUD/导出
│   ├── data/
│   │   ├── schema.sql               ← 建表 SQL（4 表 + 索引）
│   │   └── team_aliases.json        ← 球队别名映射表（16 支球队）
│   ├── tests/
│   │   ├── test_data_importer.py
│   │   ├── test_data_cleaner.py
│   │   └── test_fact_generator.py
│   └── requirements.txt
├── raw_data/
│   ├── matches_2018_sample.csv      ← 11 场 2018 世界杯样例
│   └── matches_2022_sample.json     ← 6 场 2022 世界杯样例
├── scripts/
│   ├── import_data.py               ← 一键导入脚本
│   └── validate_data.py             ← 数据质量校验
└── C成员开发指导文档.md              ← 本文档
```

---

## 三、快速开始

```bash
pip install -r backend/requirements.txt

# 导入 CSV 样例数据
python scripts/import_data.py \
  --input raw_data/matches_2018_sample.csv \
  --source_type csv --year 2018 --host "俄罗斯"

# 导入 JSON 样例数据
python scripts/import_data.py \
  --input raw_data/matches_2022_sample.json \
  --source_type json --year 2022 --host "卡塔尔"

# 校验数据质量
python scripts/validate_data.py --db backend/data/worldcup.db

# 运行测试
cd backend
python -m pytest tests/ -v
```

---

## 四、核心数据表

### 4.1 四张表关系

```
tournaments (届次)          teams (球队)
     │                         │
     │    matches (比赛)        │
     │    ┌─────────────────────┤
     │    │ home_team_id        │
     │    │ away_team_id        │
     │    │ winner_team_id      │
     │    └─────────────────────┤
     │                         │
     └──── tournament_year ────┘
              │
         sources (来源)
              │
         source_id
```

### 4.2 Match 表关键字段

| 字段组 | 字段 | 说明 |
|--------|------|------|
| 赛事定位 | `tournament_year`, `match_date`, `stage`, `group_name`, `venue` | 唯一确定一场比赛 |
| 参赛双方 | `home_team_id`, `away_team_id` | 关联 teams 表，不存队名 |
| 90 分钟 | `home_score_90`, `away_score_90` | 常规时间比分 |
| 加时后 | `home_score_et`, `away_score_et` | 加时结束累计比分（可 NULL） |
| 点球 | `home_penalties`, `away_penalties` | 仅点球大战有值（可 NULL） |
| 结果 | `winner_team_id`, `result_type`, `score_display` | 胜者 + 类型 + 显示比分 |

---

## 五、比分口径规则

```
判断优先级：点球 > 加时 > 常规分出胜负 > 平局

1. 有点球数据  → result_type = "penalties"
   score_display = "3:3 (点球 4:2)"

2. 有加时比分且 ≠ 90分钟比分 → result_type = "extra_time"
   score_display = "2:1"（加时结束累计比分）

3. 只有 90 分钟比分且 ≠ → result_type = "regulation"
   score_display = "4:2"

4. 90 分钟比分 = 且无加时/点球 → result_type = "draw"
   score_display = "1:1"
```

---

## 六、球队别名归一

### 6.1 匹配优先级

```
精确匹配（大小写敏感）→ 大小写不敏感 → 模糊匹配（包含关系）→ 失败
```

### 6.2 别名示例

| 原始输入 | 匹配结果 | 匹配方式 |
|---------|---------|---------|
| "法国" | team_FRA | 精确 |
| "France" | team_FRA | 精确 |
| "法兰西" | team_FRA | 精确（已收录） |
| "荷兰队" | team_NED | 模糊（包含"荷兰"） |
| "西德" | team_GER | 精确（历史名称已收录） |

### 6.3 新增球队流程

1. 在 `team_aliases.json` 的 `aliases` 中添加新条目
2. 在 `teams` 中添加规范信息
3. 重新运行导入脚本

---

## 七、事实文本模板

四种 `result_type` 对应四种中文模板：

| 类型 | 示例输出 |
|------|---------|
| regulation | `2018年世界杯决赛，法国队在卢日尼基体育场以4:2战胜克罗地亚队，常规时间结束即分出胜负。` |
| extra_time | `2018年世界杯半决赛，克罗地亚队...90分钟内1:1战平，加时赛后克罗地亚队以2:1获胜。` |
| penalties | `2022年世界杯决赛，阿根廷队...常规及加时赛3:3战平，点球大战阿根廷队4:2胜出晋级。` |
| draw | `2018年世界杯小组赛，葡萄牙队与西班牙队3:3战平。` |

---

## 八、清洗报告格式

导入脚本自动生成 `cleaning_report.json`：

```json
{
  "summary": {"total_records": 11, "valid": 10, "fixed": 1, "rejected": 0},
  "warnings": [
    {"match_id": "...", "field": "match_date", "value": "2018/07/15",
     "action": "normalized:2018/07/15→2018-07-15"}
  ],
  "errors": [
    {"match_id": "...", "field": "home_team", "value": "火星队",
     "reason": "无法识别主队名称: 火星队"}
  ]
}
```

---

## 九、与成员 D、E 的接口

### 给 D（Chroma）
- `generate_all_match_facts()` 返回 `list[dict]`，每条含 `text`（事实文本）和 `metadata`（match_id / year / stage / team_ids / result_type / source_id）
- `export_matches_to_json()` 导出完整比赛数据 JSON

### 给 E（RAG & 评测）
- SQLite 数据库：E 可直接 SQL 查询结构化事实验证 answer 准确性
- 清洗报告：E 在实验报告中引用数据质量指标

---

## 十、常见问题

**Q: 为什么用 SQLite 而不是直接给 dict？**  
A: 结构化查询（"法国队在 2018 年淘汰赛击败了哪些球队"）需要 SQL 的 WHERE/JOIN，纯 dict 无法高效实现。

**Q: 西德和德国怎么处理？**  
A: 西德在别名表中映射到 team_GER，与统一后的德国共用同一 team_id。历史名称保留在 aliases 中。

**Q: 点球大战的胜者算"获胜"吗？**  
A: result_type 区分统计。`result_type=penalties` 表示点球晋级，查询"获胜场次"时可选择是否计入。

**Q: 新增赛事届次要改代码吗？**  
A: 不需要。只需提供新的 CSV/JSON 数据文件，运行导入脚本即可。

---

## 十一、交付检查清单

- [x] `models/entities.py` — 4 张核心表的 dataclass + CleaningReport
- [x] `data/schema.sql` — 建表 SQL（含 CHECK 约束和索引）
- [x] `data/team_aliases.json` — 16 支球队的别名映射
- [x] `services/data_importer.py` — CSV/JSON/PDF 导入 + 字段校验
- [x] `services/data_cleaner.py` — 队名归一 + 日期/阶段/比分清洗 + 一致性校验
- [x] `services/fact_generator.py` — 4 种结果类型的模板化事实生成
- [x] `services/db_schema.py` — SQLite 建表 + CRUD + 批量导入 + 导出
- [x] `scripts/import_data.py` — 一键导入（读取→清洗→入库→生成事实文本）
- [x] `scripts/validate_data.py` — 数据质量校验（比分逻辑/球队引用/重复/来源）
- [x] `raw_data/` — CSV + JSON 样例数据（共 17 场比赛）
- [x] `tests/` — 3 个测试文件（导入/清洗/事实生成）
- [x] `requirements.txt` — 依赖清单
- [ ] 运行测试并截图
- [ ] 与成员 B 确认 API JSON 契约
- [ ] 与成员 D 确认事实文本 metadata 格式
- [ ] 清洗报告截图（放入报告）
