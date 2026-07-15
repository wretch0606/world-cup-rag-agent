# 团队协作规范

## 标准工作流

1. 先创建或认领 Issue，写清目标、验收标准和负责人。
2. 从最新 `develop` 创建个人功能分支。
3. 小步提交，每个提交只解决一个明确问题。
4. 推送分支并向 `develop` 创建 Pull Request。
5. 至少一名组员审查通过、自动检查通过后再合并。
6. 联调与阶段验收通过后，由组长创建 `develop -> main` 的发布 PR。

## 分支命名

- `feature/<scope>`：新功能，例如 `feature/retrieval`
- `fix/<scope>`：普通修复，例如 `fix/score-parser`
- `hotfix/<scope>`：紧急修复，例如 `hotfix/demo-crash`
- `docs/<scope>`：文档，例如 `docs/api-contract`
- `test/<scope>`：测试或评测，例如 `test/rag-benchmark`
- `chore/<scope>`：工程维护，例如 `chore/ci`

名称使用小写英文和连字符，不使用姓名或模糊名称（如 `dev1`、`new`、`temp`）。

## Commit 规范

格式：`<type>(<scope>): <summary>`

常用类型：`feat`、`fix`、`docs`、`test`、`refactor`、`chore`。

示例：

```text
feat(retrieval): add hybrid match lookup
fix(data): normalize penalty shootout scores
docs(api): document answer citation schema
```

## Pull Request 要求

- PR 标题使用与 Commit 相同的格式。
- 描述必须包含改动目的、主要实现、验证结果和关联 Issue。
- PR 尽量控制在一个功能点内；过大时拆分。
- 不提交密钥、令牌、个人配置、模型缓存、向量库文件或大体积原始数据。
- API 或数据结构变更必须同步更新 `docs/`。
- 合并前先同步 `develop`，解决冲突并重新运行测试。

## 评审重点

- 事实答案是否可追溯到结构化数据或证据片段。
- 是否区分常规时间、加时赛与点球大战比分。
- 数据主键、球队别名、届次和阶段是否规范化。
- 检索、重排和生成是否可独立测试。
- 是否包含异常处理、日志与必要的测试。

