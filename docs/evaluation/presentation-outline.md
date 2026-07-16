# 答辩 PPT 逐页提纲

建议 12-14 页，控制在 8-10 分钟。每页只表达一个核心结论。

## 第1页：标题页

- 标题：基于 Chroma 与 LangGraph 的世界杯知识库多 Agent 问答系统
- 副标题：RAG 事实融合与评测
- 成员、课程、小组、日期

## 第2页：为什么不能只用向量检索

- 核心结论：比分、胜负、加时和点球是强结构化事实。
- 展示：一个“正式比分3:3、点球4:2”的错误与正确回答对比。
- 讲解重点：纯文本相似度可能召回相关内容，但不能保证计算口径。

## 第3页：系统总体架构

- 展示：用户 → 总 Agent → SQL/Chroma → reranker → E事实融合 → 前端。
- 高亮 E 负责部分：Prompt、事实融合、来源引用、异常处理和评测。

## 第4页：输入输出契约

- 左侧：结构化事实与 D 返回的检索候选。
- 右侧：`answer`、`facts`、`sources`、`confidence`、`warnings`。
- 强调：`source_id` 全链路保留。

## 第5页：六类 Prompt 设计

- 精确比分、胜负关系、点球、比较、总结、fallback。
- 每类只展示一条最关键规则。
- 重点示例：点球 Prompt 分离 `score_display` 与 `penalty_score`。

## 第6页：测试集设计

- 展示：30 道题，六类各 5 题。
- 展示字段：`gold_facts`、`must_mention`、`must_not_contain`、`required_source_ids`。
- 说明：正式实验前由 C 复核标准事实和来源。

## 第7页：评测指标

- Intent Accuracy
- Fact Accuracy
- Citation Coverage
- Penalty Scope Accuracy
- Faithfulness / Completeness / Readability
- Average Latency

## 第8页：实验配置

- E0 基线
- E1 + query rewrite
- E2 + reranker
- E3 结构化库 + Chroma
- E4 不同 Top-K
- E5 Prompt 优化

建议用一张配置矩阵，不要放大段文字。

## 第9页：总体实验结果

- 从 Excel“指标汇总”生成柱状图或雷达图。
- 高亮最佳配置和是否达到验收目标。
- 素材位置：`assets/overall_results.png`

## 第10页：消融实验结果

- query rewrite 带来的 Recall/MRR 变化。
- reranker 带来的 Top-3 相关率/nDCG 变化。
- 混合方案带来的事实准确率变化。
- 同时展示延迟代价。

## 第11页：成功案例

- 问题：2022年世界杯决赛正式比分与点球比分。
- 展示结构化事实、检索证据和最终回答。
- 标记答案如何引用 `source_id`。

## 第12页：错误案例与修复

- 展示一次真实失败：错误回答、原因定位、Prompt/检索修复和回归结果。
- 优先选择点球口径、来源冲突或无结果编造案例。

## 第13页：现场演示流程

1. 精确比分问题
2. 胜负关系问题
3. 点球语义问题
4. 越界问题

每一步提前准备问题、预期结果和失败备用截图。

## 第14页：结论与后续工作

- 结论：结构化事实负责精确，Chroma 负责语义与证据。
- 已达到的指标：[待填写]
- 当前限制：[测试集规模、数据覆盖、模型延迟]
- 后续：[扩展历届数据、自动裁判、更多冲突数据]

## 备用页

- JSON 接口完整示例
- 30 道测试题分布
- Prompt 完整规则
- 错误类型统计
- 运行环境和复现命令
