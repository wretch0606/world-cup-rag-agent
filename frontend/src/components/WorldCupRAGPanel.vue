<template>
  <div class="app-layout">
    <!-- ====== 左侧筛选栏 ====== -->
    <FilterSidebar
      v-model:filters="filtersState"
      :filter-options="filterOptions"
      :loading="pageLoading"
      @reset="handleFilterReset"
    />

    <!-- ====== 右侧主内容区 ====== -->
    <main class="main-area">
      <!-- ============================================================== -->
      <!-- 上半部分：问答区 + D3 图谱                                     -->
      <!-- ============================================================== -->
      <div class="top-row">
        <!-- ---- 问答区 ---- -->
        <section class="qa-section">
          <div class="qa-scroll">
            <!-- ====== 页面初始加载态 ====== -->
            <div v-if="pageLoading" class="qa-state-box">
              <span class="qa-spinner"></span>
              <p>{{ stateLabels.loadingPage }}</p>
            </div>

            <!-- ====== 筛选选项加载失败 ====== -->
            <div v-else-if="filterOptionsError" class="qa-state-box qa-state-error">
              <span class="qa-state-icon">⚠️</span>
              <p>{{ stateLabels.filterLoadError }}</p>
              <button class="qa-retry-btn" @click="initPage">重新加载</button>
            </div>

            <!-- ====== 正常内容 ====== -->
            <template v-else>
              <!-- 用户提问展示条 -->
              <div class="user-question-bar">
                <span class="question-icon">💬</span>
                <span class="question-label">{{ qaLabels.questionPrefix }}</span>
                <span class="question-text">{{ currentUserQuestion }}</span>
              </div>

              <!-- ====== QA 加载态 ====== -->
              <div v-if="queryLoading" class="qa-state-box qa-thinking">
                <span class="qa-thinking-dot"></span>
                <span class="qa-thinking-dot"></span>
                <span class="qa-thinking-dot"></span>
                <p>{{ stateLabels.thinking }}</p>
              </div>

              <!-- ====== QA HTTP 错误 ====== -->
              <div v-else-if="queryError" class="qa-state-box qa-state-error">
                <span class="qa-state-icon">⚠️</span>
                <p>{{ stateLabels.queryError }}</p>
                <button class="qa-retry-btn" @click="handleSendQuestion">重新发送</button>
              </div>

              <!-- ====== 无结果（empty） ====== -->
              <div
                v-else-if="queryResult && queryResult.status === 'empty'"
                class="qa-state-box"
              >
                <span class="qa-state-icon">🔍</span>
                <p>{{ stateLabels.empty }}</p>
                <div
                  v-if="queryResult.warnings && queryResult.warnings.length"
                  class="qa-warnings"
                >
                  <p
                    v-for="w in queryResult.warnings"
                    :key="w.code"
                    class="qa-warning-item"
                  >
                    ⚠ {{ w.message }}
                  </p>
                </div>
              </div>

              <!-- ====== 需要澄清 ====== -->
              <div v-else-if="needsClarification" class="qa-state-box qa-state-clarify">
                <span class="qa-state-icon">💡</span>
                <p>{{ clarificationMessage }}</p>
              </div>

              <!-- ====== 正常 / 降级结果 ====== -->
              <template v-else-if="queryResult">
                <!-- 降级告警横幅 -->
                <div
                  v-if="queryResult.status === 'degraded' && queryResult.warnings && queryResult.warnings.length"
                  class="qa-warning-banner"
                >
                  <span class="qa-warning-banner-icon">⚠️</span>
                  <div class="qa-warning-banner-list">
                    <p v-for="w in queryResult.warnings" :key="w.code">
                      <strong>[{{ w.code }}]</strong> {{ w.message }}
                    </p>
                  </div>
                </div>

                <!-- 意图 Badge -->
                <div class="intent-badges">
                  <span class="badge-label">{{ intentLabels.title }}</span>
                  <span
                    v-for="badge in intentBadges"
                    :key="badge.key"
                    :class="['badge', badge.css]"
                  >
                    <span class="badge-key">{{ badge.key }}</span>
                    <span class="badge-sep">:</span>
                    <span class="badge-val">{{ badge.val }}</span>
                  </span>
                </div>

                <!-- 核心事实表 -->
                <div v-if="queryResult.facts.length" class="fact-panel">
                  <h4 class="panel-title">{{ factLabels.title }}</h4>
                  <table class="fact-table">
                    <tbody>
                      <tr v-for="row in factRows" :key="row.label">
                        <td class="fact-label">{{ row.label }}</td>
                        <td class="fact-value">
                          <span v-if="row.label === factRows[factRows.length - 1].label" class="champion-crown">🏆</span>
                          {{ row.value }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- 引用来源 -->
                <div v-if="queryResult.sources.length" class="sources-panel">
                  <h4 class="panel-title">{{ sourceLabels.title }}</h4>
                  <div class="sources-cards">
                    <div v-for="src in sourceCatalog" :key="src.source_id" class="source-card">
                      <div class="source-card-header">
                        <span class="source-card-id">{{ src.source_id }}</span>
                      </div>
                      <p class="source-card-title">{{ src.title }}</p>
                      <div class="source-card-meta">
                        <a
                          v-if="src.url"
                          :href="src.url"
                          target="_blank"
                          rel="noopener"
                          class="source-card-url"
                        >🔗 查看原文</a>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </template>
          </div>

          <!-- 底部提问输入框 -->
          <div class="qa-input-bar">
            <input
              v-model="userInputText"
              type="text"
              class="qa-input"
              :placeholder="qaLabels.inputPlaceholder"
              :disabled="queryLoading"
              @keyup.enter="handleSendQuestion"
            />
            <button
              class="qa-send-btn"
              :disabled="queryLoading"
              @click="handleSendQuestion"
            >
              {{ queryLoading ? qaLabels.sendingBtn : qaLabels.sendBtn }}
            </button>
          </div>
        </section>

        <!-- ---- D3 图谱 ---- -->
        <TeamRelationGraph :graph-data="graphResult" :loading="graphLoading" />
      </div>

      <!-- ============================================================== -->
      <!-- 下半部分：比赛时间线（自带分页）                                 -->
      <!-- ============================================================== -->
      <MatchTimeline :filters="currentFilters" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  type FiltersState,
  type QueryFilters,
  type FilterOptionsData,
  type GraphData,
  type QueryResponseData,
  type ApiSourceItem,
  fetchFilterOptions,
  fetchGraph,
  postQuery,
} from '@/api'
import FilterSidebar from './FilterSidebar.vue'
import MatchTimeline from './MatchTimeline.vue'
import TeamRelationGraph from './TeamRelationGraph.vue'

// ============================================================
// 页面级状态
// ============================================================
const pageLoading = ref(true)
const filterOptionsError = ref(false)

const stateLabels = {
  loadingPage: '正在加载数据...',
  thinking: 'AI 正在分析您的问题...',
  queryError: '请求失败，请稍后重试',
  filterLoadError: '筛选选项加载失败',
  empty: '未找到相关信息，请尝试调整问题或筛选条件',
}

// ============================================================
// 筛选状态（与 FilterSidebar v-model 双向绑定）
// ============================================================
const filtersState = ref<FiltersState>({
  years: [],
  teamIds: [],
  stages: [],
  resultTypes: [],
  hasPenalties: false,
})

const filterOptions = ref<FilterOptionsData>({
  data_status: 'mock',
  tournaments: [],
  teams: [],
  stages: [],
  result_types: [],
})

/** 将 UI 筛选状态转换为 API 查询参数 */
const currentFilters = computed<QueryFilters>(() => ({
  years: filtersState.value.years.length ? [...filtersState.value.years] : undefined,
  team_ids: filtersState.value.teamIds.length ? [...filtersState.value.teamIds] : undefined,
  stages: filtersState.value.stages.length ? [...filtersState.value.stages] : undefined,
  result_types: filtersState.value.resultTypes.length ? [...filtersState.value.resultTypes] : undefined,
  has_penalties: filtersState.value.hasPenalties || undefined,
}))

function handleFilterReset() {
  filtersState.value = {
    years: [],
    teamIds: [],
    stages: [],
    resultTypes: [],
    hasPenalties: false,
  }
}

// ============================================================
// 图谱状态（父组件负责获取，传递给子组件）
// ============================================================
function emptyGraph(): GraphData {
  return {
    data_status: 'mock',
    scope: '',
    nodes: [],
    edges: [],
    stats: { node_count: 0, edge_count: 0, truncated: false },
    applied_filters: {},
  }
}

const graphResult = ref<GraphData>(emptyGraph())
const graphLoading = ref(false)

async function loadGraph() {
  graphLoading.value = true
  try {
    graphResult.value = await fetchGraph(currentFilters.value)
  } catch {
    graphResult.value = emptyGraph()
  } finally {
    graphLoading.value = false
  }
}

// 筛选变化 → 刷新图谱
watch(currentFilters, () => loadGraph())

// ============================================================
// 问答状态（内联）
// ============================================================
const qaLabels = {
  questionPrefix: '问：',
  inputPlaceholder: '请输入您的问题...',
  sendBtn: '发送',
  sendingBtn: '分析中...',
}

const userInputText = ref('')
const currentUserQuestion = ref('2022年世界杯决赛阿根廷对法国的比分是多少？')
const queryLoading = ref(false)
const queryError = ref(false)
const queryResult = ref<QueryResponseData | null>(null)

async function handleSendQuestion() {
  const trimmed = userInputText.value.trim()
  if (!trimmed || queryLoading.value) return
  currentUserQuestion.value = trimmed
  userInputText.value = ''
  queryLoading.value = true
  queryError.value = false

  try {
    const res = await postQuery(trimmed, currentFilters.value)
    queryResult.value = res
    // QA 可能返回新图谱数据
    if (res.graph) {
      graphResult.value = res.graph
    }
  } catch {
    queryError.value = true
  } finally {
    queryLoading.value = false
  }
}

// ---- 澄清检测 ----
const needsClarification = computed(() => {
  const result = queryResult.value
  return result?.needs_clarification
    ?? result?.warnings?.some(w => w.code === 'NEED_CLARIFICATION')
    ?? false
})
const clarificationMessage = computed(() =>
  queryResult.value?.clarification_question
    ?? queryResult.value?.warnings?.find(w => w.code === 'NEED_CLARIFICATION')?.message
    ?? '请提供更多信息',
)

// ---- 意图 Badge（confidence 为 null 时隐藏置信度） ----
const intentLabels = { title: '分析结果' }

const intentBadges = computed(() => {
  const d = queryResult.value
  if (!d) return []
  const f = d.facts[0]
  const teams = f ? `${f.home_team?.name ?? '?'}, ${f.away_team?.name ?? '?'}` : '—'

  const badges = [
    { key: '意图', val: d.intent, css: 'badge-blue' },
    { key: '实体', val: teams, css: 'badge-green' },
    { key: '赛事', val: f ? `${f.stage_name}` : '—', css: 'badge-orange' },
  ]

  // MVP 阶段 confidence 为 null → 不展示置信度 badge
  if (d.confidence != null) {
    badges.push({
      key: '置信度',
      val: `${Math.round(d.confidence * 100)}%`,
      css: 'badge-purple',
    })
  }

  return badges
})

// ---- 核心事实表 ----
const factLabels = { title: '核心事实' }

interface FactRow {
  label: string
  value: string
}

const factRows = computed<FactRow[]>(() => {
  const f = queryResult.value?.facts[0]
  if (!f) return []
  const s = f.score
  const home = f.home_team?.name ?? '?'
  const away = f.away_team?.name ?? '?'
  return [
    { label: '赛事', value: f.stage_name ?? '—' },
    {
      label: '对阵',
      value: `${home} vs ${away}`,
    },
    {
      label: '常规时间',
      value: s ? `${home} ${s.regular_time.home} : ${s.regular_time.away} ${away}` : '—',
    },
    {
      label: '加时赛',
      value: s?.after_extra_time
        ? `${home} ${s.after_extra_time.home} : ${s.after_extra_time.away} ${away}`
        : '（无加时）',
    },
    {
      label: '点球',
      value: s?.penalty_display
        ? `${home} ${s.penalty_display} ${away}`
        : '（无点球大战）',
    },
    {
      label: '冠军',
      value: f.winner_team ? f.winner_team.name : '—',
    },
  ]
})

// ---- 来源卡片（source.url 为 null 时不渲染链接） ----
const sourceLabels = { title: '引用来源' }
const sourceCatalog = computed<ApiSourceItem[]>(() => queryResult.value?.sources ?? [])

// ============================================================
// 初始化
// ============================================================
async function initPage() {
  pageLoading.value = true
  filterOptionsError.value = false
  const [filtersResult, graphResultResponse] = await Promise.allSettled([
    fetchFilterOptions(),
    fetchGraph(),
  ])

  if (filtersResult.status === 'fulfilled') {
    filterOptions.value = filtersResult.value
  } else {
    filterOptionsError.value = true
  }

  if (graphResultResponse.status === 'fulfilled') {
    graphResult.value = graphResultResponse.value
  } else {
    graphResult.value = emptyGraph()
  }
  pageLoading.value = false
}

onMounted(() => initPage())
</script>

<style scoped>
/* ============================================================
   根布局
   ============================================================ */
.app-layout {
  display: flex;
  height: 100vh;
  background: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  overflow: hidden;
}

/* ---- 右侧主内容区 ---- */
.main-area {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}

/* ============================================================
   上半部分：问答 + D3 图
   ============================================================ */
.top-row {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 16px;
}

/* ---- 问答区 ---- */
.qa-section {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.qa-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ============================================================
   状态占位盒（loading / error / empty / clarify）
   ============================================================ */
.qa-state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  background: #fff;
  border: 1px solid #e0e5ec;
  border-radius: 10px;
  color: #888;
  font-size: 14px;
  text-align: center;
}

.qa-state-icon { font-size: 36px; opacity: 0.5; }

.qa-state-error {
  border-color: #f5c6cb;
  color: #c0504d;
}

.qa-state-clarify {
  border-color: #b8daff;
  background: #f0f7ff;
  color: #1a56c4;
}

.qa-retry-btn {
  padding: 8px 20px;
  border: 1px solid #c0504d;
  border-radius: 6px;
  background: #fff;
  color: #c0504d;
  cursor: pointer;
  font-size: 13px;
}
.qa-retry-btn:hover { background: #fef2f2; }

/* ---- spinner ---- */
.qa-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e0e0e0;
  border-top: 3px solid #4a90d9;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---- thinking dots ---- */
.qa-thinking {
  flex-direction: row;
  gap: 6px;
}

.qa-thinking-dot {
  width: 8px;
  height: 8px;
  background: #4a90d9;
  border-radius: 50%;
  animation: dotPulse 1.2s ease-in-out infinite;
}

.qa-thinking-dot:nth-child(1) { animation-delay: 0s; }
.qa-thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.qa-thinking-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

/* ---- 告警 ---- */
.qa-warnings {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

.qa-warning-item {
  margin: 0;
  font-size: 12px;
  color: #b85c10;
  background: #fef9e7;
  padding: 6px 10px;
  border-radius: 4px;
  text-align: left;
}

/* ---- 降级告警横幅 ---- */
.qa-warning-banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  background: #fef9e7;
  border: 1px solid #f5d78e;
  border-radius: 8px;
  font-size: 13px;
}

.qa-warning-banner-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }

.qa-warning-banner-list { display: flex; flex-direction: column; gap: 4px; }

.qa-warning-banner-list p {
  margin: 0;
  color: #8a6d3b;
  font-size: 12px;
  line-height: 1.5;
}

/* ============================================================
   用户提问展示条
   ============================================================ */
.user-question-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f7f9fc;
  border: 1px solid #e0e5ec;
  border-radius: 8px;
  font-size: 14px;
}

.question-icon { font-size: 16px; flex-shrink: 0; }
.question-label { font-weight: 700; color: #888; flex-shrink: 0; }
.question-text { color: #1a1a1a; font-weight: 500; }

/* ============================================================
   意图 Badge
   ============================================================ */
.intent-badges {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  flex-wrap: wrap;
}

.badge-label { font-size: 13px; font-weight: 700; color: #888; margin-right: 4px; }

.badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
}

.badge-key { opacity: 0.75; font-weight: 500; }
.badge-sep { opacity: 0.5; margin: 0 1px; }

.badge-blue  { background: #e8f0fe; color: #1a56c4; }
.badge-green { background: #e6f7e6; color: #1a7a2e; }
.badge-orange{ background: #fef3e5; color: #b85c10; }
.badge-purple{ background: #f3e8ff; color: #6b21a8; }

/* ============================================================
   事实面板
   ============================================================ */
.fact-panel {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
}

.panel-title {
  margin: 0 0 12px 0;
  font-size: 15px;
  font-weight: 700;
  color: #1a1a1a;
  border-left: 3px solid #4a90d9;
  padding-left: 10px;
}

.fact-table { width: 100%; border-collapse: collapse; }

.fact-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}

.fact-label {
  width: 80px;
  font-weight: 600;
  color: #888;
  white-space: nowrap;
  vertical-align: top;
}

.fact-value { color: #1a1a1a; font-weight: 500; }

.champion-crown { margin-right: 4px; }

/* ============================================================
   来源面板
   ============================================================ */
.sources-panel {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
}

.sources-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-card {
  background: #f9fafb;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 12px;
}

.source-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.source-card-id {
  font-size: 11px;
  font-weight: 700;
  color: #4a90d9;
  background: #e8f0fe;
  padding: 2px 8px;
  border-radius: 4px;
}

.source-card-title {
  margin: 0;
  font-size: 13px;
  color: #333;
  line-height: 1.4;
}

.source-card-meta {
  margin-top: 6px;
  display: flex;
  gap: 12px;
  font-size: 12px;
}

.source-card-url { color: #4a90d9; text-decoration: none; }
.source-card-url:hover { text-decoration: underline; }

/* ============================================================
   输入栏
   ============================================================ */
.qa-input-bar {
  flex-shrink: 0;
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  margin-top: auto;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}

.qa-input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.qa-input:focus { border-color: #4a90d9; }
.qa-input:disabled { background: #f5f5f5; color: #999; }

.qa-send-btn {
  padding: 10px 24px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}
.qa-send-btn:hover:not(:disabled) { background: #357abd; }
.qa-send-btn:disabled { background: #a0c4e8; cursor: not-allowed; }

/* ---- 滚动条 ---- */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #c8cdd4; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #a0a7b0; }
::-webkit-scrollbar-corner { background: transparent; }
</style>
