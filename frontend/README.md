# World Cup RAG Agent — Frontend

基于 Vue 3 + TypeScript + Vite 构建的世界杯多智能体 RAG 问答系统前端，提供筛选、问答、知识图谱可视化与比赛时间线浏览等交互能力。

## 技术栈

| 类别 | 选型 | 版本 |
|---|---|---|
| 框架 | Vue 3 (Composition API + SFC) | ^3.5.13 |
| 语言 | TypeScript | ~5.7.3 |
| 构建 | Vite | ^6.2.4 |
| 可视化 | D3.js (force simulation) | ^7.9.0 |
| 类型检查 | vue-tsc | ^2.2.8 |

## 项目结构

```
frontend/
├── index.html                  # SPA 入口 HTML
├── env.d.ts                    # Vite / Vue SFC 类型声明
├── package.json
├── tsconfig.json               # TS 严格模式, ES2020, bundler 解析
├── vite.config.ts              # Vue 插件 + @ 路径别名
└── src/
    ├── main.ts                 # 应用挂载入口
    ├── App.vue                 # 根组件
    └── components/
        └── WorldCupRAGPanel.vue # 主面板（全局单组件）
```

## 页面布局

```
┌──────────┬────────────────────────────────────────────┐
│          │  💬 问答区 (flex:1)                         │
│ 左侧筛选 │  · 用户提问展示 / 意图 Badge / 事实表 / 来源│
│ 栏 (300) │  ─────────────────────────────────────────  │
│          │  [提问输入框] ← margin-top:auto 始终触底    │
│ 届次     ├────────────────────────────────────────────┤
│ 球队     │ 🕸 D3 知识图谱 (280px)                      │
│ 阶段     │  · 力导向节点 + 带防遮挡背景的边标签        │
│ 比赛结果 ├────────────────────────────────────────────┤
│ 点球     │ 📅 横向时间线 (min-height:300)              │
│          │  · 阶段分组 → 垂直卡片列 → 点击展开详情     │
└──────────┴────────────────────────────────────────────┘
```

### 模块说明

- **左侧筛选栏** — 300px 固定宽度，独立纵向滚动。支持按届次、球队、阶段、比赛结果、是否含点球等多维组合筛选。每组可折叠，提供全选/全清快捷操作。
- **问答区** — 占据剩余高度，内容区可滚动，底部输入框通过 `margin-top:auto` 始终固定在底部。展示用户提问、意图 Badge、核心事实表（6 行）与引用来源卡片。
- **D3 知识图谱** — 使用 `d3.forceSimulation` 进行力导向布局，包含碰撞检测 (`forceCollide`) 和画布边界约束，边标签采用 `paint-order:stroke` 实现白色描边背景防重叠。
- **横向时间线** — 按阶段分组，每阶段为垂直列结构（阶段圆点 → 连接线 → 比赛卡片）。点击卡片展开比分明细面板，容器高度自适应（`min-height`），超出一屏时可纵向滚动。

## 快速开始

```bash
# 安装依赖
cd frontend
npm install

# 启动开发服务器 (默认 http://localhost:5173)
npm run dev

# 类型检查 + 生产构建
npm run build

# 预览构建产物
npm run preview
```

## API 数据契约 (v2)

组件已通过 `src/api.ts` 对接 FastAPI 的筛选、比赛、图谱、问答和来源接口。后端可通过 `FRONTEND_DATA_MODE` 在 mock 与 SQLite 数据之间切换；问答接口的精确查询使用 SQLite，语义查询可使用离线证据生成或配置的大模型生成。完整 TypeScript 契约以 `src/api.ts` 为准。

## 设计决策

- **单组件架构** — 所有 UI 逻辑集中在 `WorldCupRAGPanel.vue`，避免过早拆分。后续可抽离筛选栏、图谱、时间线等子组件。
- **Flexbox 防重叠** — 根容器 `display:flex` 左右分栏，左侧固定宽度、右侧 `flex:1`；嵌套 flex 容器通过 `min-height:0` 实现正确的滚动隔离。
- **D3 力导向** — 使用真实物理模拟（斥力 -500、连杆距离 200、碰撞半径 40、画布中心定位），而非静态布局，使图谱节点分布更均匀自然。
- **时间线结构** — HTML 阶段分组 + 垂直卡片列替代绝对定位方案，确保卡片严格对齐在所属阶段圆点正下方。

## 后续计划

- [x] 对接后端 API，并支持 mock / SQLite / RAG 运行模式
- [ ] 抽离子组件（FilterSidebar / QAPanel / GraphPanel / TimelinePanel）
- [ ] 添加路由支持（多页面 / 历史记录）
- [ ] 引入 Pinia 进行全局状态管理
- [ ] 响应式适配（移动端布局）
- [ ] 单元测试（Vitest）+ E2E 测试（Playwright）
