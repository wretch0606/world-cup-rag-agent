<template>
  <!-- ================================================================ -->
  <!-- 根容器：Flexbox 左右分栏 —— 杜绝布局重叠                        -->
  <!-- ================================================================ -->
  <div class="app-layout">

    <!-- ====== 左侧筛选栏：固定 300px，独立滚动 ====== -->
    <aside class="sidebar">
      <h3 class="sidebar-title">{{ filterLabels.title }}</h3>

      <!-- 届次 -->
      <div class="filter-block">
        <div class="filter-block-header" @click="toggleFilterGroup('tournament')">
          <span>{{ filterLabels.tournament }}</span>
          <span class="filter-arrow">{{ filterGroupOpen.tournament ? '▾' : '▸' }}</span>
        </div>
        <div v-show="filterGroupOpen.tournament" class="filter-checks">
          <label v-for="y in filterOptions.tournaments" :key="y.year" class="filter-check">
            <input type="checkbox" :value="y.year" v-model="selectedFilters.tournamentYears" />
            <span>{{ y.label }}</span>
          </label>
          <div class="filter-actions">
            <button @click="selectAllTournaments">{{ filterLabels.selectAll }}</button>
            <button @click="clearAllTournaments">{{ filterLabels.clearAll }}</button>
          </div>
        </div>
      </div>

      <!-- 球队 -->
      <div class="filter-block">
        <div class="filter-block-header" @click="toggleFilterGroup('team')">
          <span>{{ filterLabels.team }}</span>
          <span class="filter-arrow">{{ filterGroupOpen.team ? '▾' : '▸' }}</span>
        </div>
        <div v-show="filterGroupOpen.team" class="filter-checks filter-checks-scroll">
          <label v-for="t in filterOptions.teams" :key="t.team_id" class="filter-check">
            <input type="checkbox" :value="t.team_id" v-model="selectedFilters.teamIds" />
            <span>{{ t.name }}</span>
          </label>
          <div class="filter-actions">
            <button @click="selectAllTeams">{{ filterLabels.selectAll }}</button>
            <button @click="clearAllTeams">{{ filterLabels.clearAll }}</button>
          </div>
        </div>
      </div>

      <!-- 阶段 -->
      <div class="filter-block">
        <div class="filter-block-header" @click="toggleFilterGroup('stage')">
          <span>{{ filterLabels.stage }}</span>
          <span class="filter-arrow">{{ filterGroupOpen.stage ? '▾' : '▸' }}</span>
        </div>
        <div v-show="filterGroupOpen.stage" class="filter-checks">
          <label v-for="s in filterOptions.stages" :key="s.value" class="filter-check">
            <input type="checkbox" :value="s.value" v-model="selectedFilters.stages" />
            <span>{{ s.label }}</span>
          </label>
          <div class="filter-actions">
            <button @click="selectAllStages">{{ filterLabels.selectAll }}</button>
            <button @click="clearAllStages">{{ filterLabels.clearAll }}</button>
          </div>
        </div>
      </div>

      <!-- 比赛结果 -->
      <div class="filter-block">
        <div class="filter-block-header" @click="toggleFilterGroup('resultType')">
          <span>{{ filterLabels.resultType }}</span>
          <span class="filter-arrow">{{ filterGroupOpen.resultType ? '▾' : '▸' }}</span>
        </div>
        <div v-show="filterGroupOpen.resultType" class="filter-checks">
          <label v-for="r in filterOptions.result_types" :key="r.value" class="filter-check">
            <input type="checkbox" :value="r.value" v-model="selectedFilters.resultTypes" />
            <span>{{ r.label }}</span>
          </label>
        </div>
      </div>

      <!-- 点球 -->
      <div class="filter-block">
        <div class="filter-block-header">
          <span>{{ filterLabels.penaltyOnly }}</span>
        </div>
        <label class="filter-check" style="padding-left:4px">
          <input type="checkbox" v-model="selectedFilters.hasPenalties" />
          <span>{{ filterLabels.penaltyHint }}</span>
        </label>
      </div>

      <button class="sidebar-reset" @click="resetFilters">{{ filterLabels.reset }}</button>
    </aside>

    <!-- ====== 右侧主内容区：占据剩余宽度 ====== -->
    <main class="main-area">

      <!-- ============================================================== -->
      <!-- 上半部分：问答区 + D3 图                                       -->
      <!-- ============================================================== -->
      <div class="top-row">

        <!-- ---- 问答区 ---- -->
        <section class="qa-section">
          <!-- 可滚动内容区：用户提问 + Badge + 事实表 + 来源 -->
          <div class="qa-scroll">
            <!-- 用户提问展示条 -->
            <div class="user-question-bar">
              <span class="question-icon">💬</span>
              <span class="question-label">{{ qaLabels.questionPrefix }}</span>
              <span class="question-text">{{ currentUserQuestion }}</span>
            </div>

            <!-- 意图标签 Badge 行 —— 仅在有问答结果时显示 -->
            <div v-if="queryResult" class="intent-badges">
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

            <!-- 核心事实表：6 行纵向结构 —— 仅在有事实数据时显示 -->
            <div v-if="queryResult && queryResult.facts.length" class="fact-panel">
              <h4 class="panel-title">{{ factLabels.title }}</h4>
              <table class="fact-table">
                <tbody>
                  <tr v-for="row in factRows" :key="row.label">
                    <td class="fact-label">{{ row.label }}</td>
                    <td class="fact-value">
                      <span v-if="row.label === factRows[5].label" class="champion-crown">🏆</span>
                      {{ row.value }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 引用来源卡片 —— 仅在有来源数据时显示 -->
            <div v-if="queryResult && queryResult.sources.length" class="sources-panel">
              <h4 class="panel-title">{{ sourceLabels.title }}</h4>
              <div class="sources-cards">
                <div v-for="src in sourceCatalog" :key="src.source_id" class="source-card">
                  <div class="source-card-header">
                    <span class="source-card-id">{{ src.source_id }}</span>
                  </div>
                  <p class="source-card-title">{{ src.title }}</p>
                  <div class="source-card-meta">
                    <a v-if="src.url" :href="src.url" target="_blank" rel="noopener" class="source-card-url">🔗 查看原文</a>
                  </div>
                </div>
              </div>
            </div>
          </div><!-- /.qa-scroll -->

          <!-- 底部提问输入框：固定在问答区底部，不随滚动 -->
          <div class="qa-input-bar">
            <input
              v-model="userInputText"
              type="text"
              class="qa-input"
              :placeholder="qaLabels.inputPlaceholder"
              @keyup.enter="handleSendQuestion"
            />
            <button class="qa-send-btn" @click="handleSendQuestion">
              {{ qaLabels.sendBtn }}
            </button>
          </div>
        </section>

        <!-- ---- D3 图 ---- -->
        <aside class="graph-section">
          <h4 class="panel-title">{{ graphLabels.title }}</h4>
          <div id="d3-graph-container" class="d3-box"></div>
          <div class="graph-legend">
            <h5>{{ graphLabels.legendTitle }}</h5>
            <div class="legend-row"><span class="leg-dot"></span><span>{{ graphLabels.nodeDesc }}</span></div>
            <div class="legend-row"><span class="leg-line"></span><span>{{ graphLabels.edgeDesc }}</span></div>
            <div class="legend-row"><span class="leg-arrow">→</span><span>{{ graphLabels.arrowDesc }}</span></div>
            <div class="legend-fmt">
              <p>{{ graphLabels.edgeFormatDesc }}</p>
              <code>{{ graphLabels.edgeFormatExample }}</code>
            </div>
          </div>
        </aside>
      </div>

      <!-- ============================================================== -->
      <!-- 下半部分：横向时间线 + 展开比分明细卡片                         -->
      <!-- ============================================================== -->
      <section class="timeline-section">
        <h3 class="panel-title">{{ timelineLabels.title }}</h3>

        <!-- 横向滚动跟踪 -->
        <div class="tl-scroll">
          <div class="tl-track">
            <div class="tl-spine"></div>

            <template v-for="stage in timelineStages" :key="stage.stage">
              <div class="tl-group">
                <!-- 阶段标记：蓝色小圆圈 + 阶段名 -->
                <div class="tl-stage">
                  <span class="tl-dot"></span>
                  <span class="tl-stage-name">{{ stage.stage_name }}</span>
                </div>

                <!-- 连接线：从圆圈向下延伸 -->
                <span class="tl-stage-conn"></span>

                <!-- 比赛卡片：在该阶段圆圈正下方垂直罗列 -->
                <div class="tl-cards">
                  <div
                    v-for="m in stage.matches"
                    :key="m.match_id"
                    :class="['tl-match', { 'tl-active': expandedMatchId === m.match_id }]"
                    @click="toggleMatchDetail(m.match_id)"
                  >
                    <div class="tl-card">
                      <span class="tl-teams">{{ m.home_team_name }} vs {{ m.away_team_name }}</span>
                      <span class="tl-score">
                        {{ m.score.display }}
                        <span v-if="m.score.penalty_display" class="tl-pk">({{ m.score.penalty_display }})</span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- 展开的比分明细面板 -->
        <div v-if="expandedMatchDetail" class="tl-detail">
          <div class="tl-detail-head">
            <h4>
              {{ expandedMatchDetail.home_team_name }}
              <span class="tl-vs">vs</span>
              {{ expandedMatchDetail.away_team_name }}
              <span class="tl-tag">{{ expandedMatchDetail.stage_name }}</span>
              <span class="tl-tag tl-tag-year">{{ expandedMatchDetail.tournament_year }}</span>
            </h4>
            <button @click="closeMatchDetail">✕ {{ timelineLabels.close }}</button>
          </div>

          <div class="tl-detail-body">
            <!-- 90 分钟 -->
            <div class="tl-score-card">
              <h5>{{ timelineLabels.regularTime }}</h5>
              <div class="tl-score-row">
                <span class="tl-team-name">{{ expandedMatchDetail.home_team_name }}</span>
                <span class="tl-big-score">{{ expandedMatchDetail.score.regular_time.home }}</span>
                <span class="tl-colon">:</span>
                <span class="tl-big-score">{{ expandedMatchDetail.score.regular_time.away }}</span>
                <span class="tl-team-name">{{ expandedMatchDetail.away_team_name }}</span>
              </div>
            </div>

            <!-- 加时赛 -->
            <div class="tl-score-card">
              <h5>{{ timelineLabels.extraTime }}</h5>
              <div class="tl-score-row">
                <span class="tl-team-name">{{ expandedMatchDetail.home_team_name }}</span>
                <span class="tl-big-score">{{ expandedMatchDetail.score.after_extra_time?.home ?? '—' }}</span>
                <span class="tl-colon">:</span>
                <span class="tl-big-score">{{ expandedMatchDetail.score.after_extra_time?.away ?? '—' }}</span>
                <span class="tl-team-name">{{ expandedMatchDetail.away_team_name }}</span>
              </div>
              <p v-if="!expandedMatchDetail.score.after_extra_time" class="tl-na">{{ timelineLabels.notApplicable }}</p>
              <p v-else class="tl-summary">{{ timelineLabels.formalScore }}{{ expandedMatchDetail.score.display }}</p>
            </div>

            <!-- 点球大战 -->
            <div class="tl-score-card">
              <h5>{{ timelineLabels.penaltyShootout }}</h5>
              <div class="tl-score-row">
                <span class="tl-team-name">{{ expandedMatchDetail.home_team_name }}</span>
                <span class="tl-big-score">{{ expandedMatchDetail.score.penalties?.home ?? '—' }}</span>
                <span class="tl-colon">:</span>
                <span class="tl-big-score">{{ expandedMatchDetail.score.penalties?.away ?? '—' }}</span>
                <span class="tl-team-name">{{ expandedMatchDetail.away_team_name }}</span>
              </div>
              <p v-if="!expandedMatchDetail.score.penalties" class="tl-na">{{ timelineLabels.notApplicable }}</p>
              <p v-else class="tl-summary">{{ timelineLabels.penaltyScoreLabel }}{{ expandedMatchDetail.score.penalty_display }}</p>
            </div>

            <!-- 来源 -->
            <div class="tl-score-card tl-src-card">
              <h5>{{ timelineLabels.sourceDetails }}</h5>
              <ul v-if="expandedMatchDetail.sources.length" class="tl-src-list">
                <li v-for="s in expandedMatchDetail.sources" :key="s.source_id" class="tl-src-item">
                  <span class="tl-src-id">[{{ s.source_id }}]</span>
                  <span>{{ s.title }}</span>
                  <a v-if="s.url" :href="s.url" target="_blank" rel="noopener">🔗</a>
                </li>
              </ul>
              <p v-else class="tl-na">{{ timelineLabels.noSource }}</p>
            </div>
          </div>
        </div>
      </section>

    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import * as d3 from 'd3'
import {
  type QueryFilters,
  type MatchItem,
  type GraphData,
  type FilterOptionsData,
  type QueryResponseData,
  type ApiSourceItem,
  fetchFilterOptions,
  fetchMatches,
  fetchGraph,
  postQuery,
} from '@/api'

// ============================================================
// 1. 筛选栏
// ============================================================
const filterLabels = {
  title: '筛选条件',
  tournament: '世界杯届次',
  team: '球队',
  stage: '比赛阶段',
  resultType: '比赛结果',
  penaltyOnly: '仅看点球',
  penaltyHint: '只显示包含点球大战的比赛',
  reset: '重置筛选',
  selectAll: '全选',
  clearAll: '清空',
}

const filterGroupOpen = reactive({
  tournament: true,
  team: false,
  stage: true,
  resultType: false,
})

function toggleFilterGroup(k: keyof typeof filterGroupOpen) { filterGroupOpen[k] = !filterGroupOpen[k] }

/** 筛选选项 —— 由 GET /api/filter-options 填充 */
const filterOptions = ref<FilterOptionsData>({
  data_status: 'mock',
  tournaments: [],
  teams: [],
  stages: [],
  result_types: [],
})

const selectedFilters = reactive({
  tournamentYears: [] as number[],
  teamIds: [] as string[],
  stages: [] as string[],
  resultTypes: [] as string[],
  hasPenalties: false,
})

function selectAllTournaments() { selectedFilters.tournamentYears = filterOptions.value.tournaments.map(t => t.year) }
function clearAllTournaments() { selectedFilters.tournamentYears = [] }
function selectAllTeams() { selectedFilters.teamIds = filterOptions.value.teams.map(t => t.team_id) }
function clearAllTeams() { selectedFilters.teamIds = [] }
function selectAllStages() { selectedFilters.stages = filterOptions.value.stages.map(s => s.value) }
function clearAllStages() { selectedFilters.stages = [] }
function resetFilters() {
  selectedFilters.tournamentYears = []
  selectedFilters.teamIds = []
  selectedFilters.stages = []
  selectedFilters.resultTypes = []
  selectedFilters.hasPenalties = false
}

// ============================================================
// 2. 问答区
// ============================================================
const qaLabels = {
  questionPrefix: '问：',
  inputPlaceholder: '请输入您的问题...',
  sendBtn: '发送',
}

const userInputText = ref('')
const currentUserQuestion = ref('2022年世界杯决赛阿根廷对法国的比分是多少？')

/** POST /api/agent/query 的响应 */
const queryResult = ref<QueryResponseData | null>(null)

async function handleSendQuestion() {
  const trimmed = userInputText.value.trim()
  if (!trimmed) return
  currentUserQuestion.value = trimmed
  userInputText.value = ''

  const filters = currentFilters()
  const res = await postQuery(trimmed, filters)
  if (res) {
    queryResult.value = res
    // 问答结果可能携带新的 graph 数据，同步到图谱
    if (res.graph) {
      graphResult.value = res.graph
    }
  }
}

// ---- 意图 Badge（置信度 null 时不显示该 badge） ----
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
    badges.push({ key: '置信度', val: `${Math.round(d.confidence * 100)}%`, css: 'badge-purple' })
  }

  return badges
})

// ---- 核心事实表 ----
const factLabels = { title: '核心事实' }

interface FactRow { label: string; value: string }

const factRows = computed<FactRow[]>(() => {
  const f = queryResult.value?.facts[0]
  if (!f) return []
  const s = f.score
  const h = f.home_team?.name ?? '?'
  const a = f.away_team?.name ?? '?'
  return [
    { label: '赛事',     value: `${f.stage_name}` },
    { label: '对阵',     value: `${h} vs ${a}` },
    { label: '常规时间', value: s ? `${h} ${s.regular_time.home} : ${s.regular_time.away} ${a}` : '—' },
    { label: '加时赛',   value: s?.after_extra_time ? `${h} ${s.after_extra_time.home} : ${s.after_extra_time.away} ${a}` : '（无加时）' },
    { label: '点球',     value: s?.penalty_display ? `${h} ${s.penalty_display} ${a}` : '（无点球大战）' },
    { label: '冠军',     value: f.winner_team ? f.winner_team.name : '—' },
  ]
})

// ---- 来源卡片 ----
const sourceLabels = { title: '引用来源' }
const sourceCatalog = computed<ApiSourceItem[]>(() => queryResult.value?.sources ?? [])

// ============================================================
// 3. 比赛时间线
// ============================================================
const timelineLabels = {
  title: '比赛时间线', close: '关闭',
  regularTime: '🕐 90 分钟常规时间', extraTime: '🕑 加时赛', penaltyShootout: '⚽ 点球大战',
  sourceDetails: '📖 来源详情', notApplicable: '本场比赛无此阶段',
  formalScore: '正式比分：', penaltyScoreLabel: '点球比分：', noSource: '暂无来源信息',
}

interface TSource { source_id: string; title: string; url: string | null }
interface TMatch {
  match_id: string; match_date: string | null; tournament_year: number
  stage: string; stage_name: string
  home_team_name: string; away_team_name: string
  score: {
    regular_time: { home: number; away: number }
    after_extra_time: { home: number; away: number } | null
    penalties: { home: number; away: number } | null
    display: string
    penalty_display: string | null
  }
  sources: TSource[]
}
interface TStage { stage: string; stage_name: string; matches: TMatch[] }

/** 将契约 MatchItem（嵌套结构）映射为 UI TMatch */
function toTMatch(m: import('@/api').MatchItem): TMatch {
  return {
    match_id: m.match_id,
    match_date: m.match_date,
    tournament_year: m.tournament_year,
    stage: m.stage,
    stage_name: m.stage_name,
    home_team_name: m.home_team?.name ?? '',
    away_team_name: m.away_team?.name ?? '',
    score: {
      regular_time: m.score.regular_time,
      after_extra_time: m.score.after_extra_time,
      penalties: m.score.penalties,
      display: m.score.display,
      penalty_display: m.score.penalty_display,
    },
    sources: [],
  }
}

/** GET /api/matches 返回的原始数据 */
const allMatches = ref<MatchItem[]>([])

/** 阶段排序（映射 stage enum 到展示顺序） */
const STAGE_ORDER: Record<string, number> = {
  group: 0, second_group: 1, round_of_16: 2, quarter_final: 3,
  semi_final: 4, third_place: 5, final: 6, final_round: 7,
}

const timelineStages = computed<TStage[]>(() => {
  const groups = new Map<string, TMatch[]>()
  for (const m of allMatches.value) {
    const tm = toTMatch(m)
    const key = m.stage
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(tm)
  }

  // 按比赛阶段排序
  return Array.from(groups.entries())
    .sort((a, b) => (STAGE_ORDER[a[0]] ?? 99) - (STAGE_ORDER[b[0]] ?? 99))
    .map(([stage, matches]) => ({
      stage,
      stage_name: matches[0].stage_name,
      matches,
    }))
})

const expandedMatchId = ref<string | null>(null)

function findTMatch(id: string): TMatch | null {
  for (const s of timelineStages.value) {
    const f = s.matches.find(m => m.match_id === id)
    if (f) return f
  }
  return null
}

const expandedMatchDetail = computed<TMatch | null>(() =>
  expandedMatchId.value ? findTMatch(expandedMatchId.value) : null,
)
function toggleMatchDetail(id: string) { expandedMatchId.value = expandedMatchId.value === id ? null : id }
function closeMatchDetail() { expandedMatchId.value = null }

// ============================================================
// 4. D3 知识图谱
// ============================================================
const graphLabels = {
  title: '球队关系图谱', legendTitle: '图例说明',
  nodeDesc: '节点 = 球队实体', edgeDesc: '连线 = 比赛（有向边）', arrowDesc: '方向 = 胜方 → 败方',
  edgeFormatDesc: '连线标签格式：', edgeFormatExample: '2022·决赛·3:3（点球4:2）',
}

/** GET /api/graph 返回的图谱数据 */
const graphResult = ref<GraphData>({ data_status: 'mock', scope: '', nodes: [], edges: [], stats: { node_count: 0, edge_count: 0, truncated: false }, applied_filters: {} })

function initD3Graph() {
  const el = document.getElementById('d3-graph-container')
  if (!el) return

  const nodes = graphResult.value.nodes
  const edges = graphResult.value.edges
  if (!nodes.length) return

  const width = 400, height = 280
  const colors = ['#4A90D9', '#E07B39', '#5D9C6E', '#C0504D', '#8064A2', '#F2A640']

  // 深拷贝 + 注入 D3 力仿真所需字段
  const simNodes: any[] = nodes.map(n => ({ ...n }))
  const simEdges: any[] = edges.map(e => ({ ...e }))

  // 清空容器
  el.innerHTML = ''

  const svg = d3.select(el)
    .append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('class', 'd3-svg')
    .attr('width', '100%')
    .attr('height', '100%')

  // 箭头标记
  svg.append('defs')
    .append('marker')
    .attr('id', 'ah')
    .attr('viewBox', '0 0 10 7')
    .attr('refX', 10)
    .attr('refY', 3.5)
    .attr('markerWidth', 6)
    .attr('markerHeight', 4)
    .attr('orient', 'auto')
    .append('polygon')
    .attr('points', '0 0,10 3.5,0 7')
    .attr('fill', '#999')

  // 连线
  const link = svg.append('g')
    .selectAll('line')
    .data(simEdges)
    .join('line')
    .attr('stroke', '#999')
    .attr('stroke-width', 1.6)
    .attr('marker-end', 'url(#ah)')

  // 节点圆
  const node = svg.append('g')
    .selectAll('circle')
    .data(simNodes)
    .join('circle')
    .attr('r', 26)
    .attr('fill', (_d: any, i: number) => colors[i % 6])
    .attr('opacity', 0.88)
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  // 节点标签
  const label = svg.append('g')
    .selectAll('text')
    .data(simNodes)
    .join('text')
    .text((d: any) => d.name)
    .attr('text-anchor', 'middle')
    .attr('fill', '#fff')
    .attr('font-size', 13)
    .attr('font-weight', 600)
    .attr('dy', 5)

  // 连线标签（强描边背景，彻底解决交叉文字重叠）
  const edgeLabel = svg.append('g')
    .selectAll('text')
    .data(simEdges)
    .join('text')
    .text((d: any) => d.label)
    .attr('text-anchor', 'middle')
    .attr('fill', '#333')
    .attr('font-size', 9)
    .attr('font-weight', 600)
    .attr('paint-order', 'stroke')
    .attr('stroke', 'rgba(255,255,255,0.92)')
    .attr('stroke-width', 4)
    .attr('stroke-linecap', 'round')
    .attr('stroke-linejoin', 'round')

  // 力仿真
  d3.forceSimulation(simNodes)
    .force('link', d3.forceLink(simEdges).id((d: any) => d.id).distance(200))
    .force('charge', d3.forceManyBody().strength(-500))
    .force('collide', d3.forceCollide().radius(40))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .on('tick', () => {
      // 节点边界约束：防止溢出画布
      const R = 26
      node
        .attr('cx', (d: any) => {
          d.x = Math.max(R, Math.min(width - R, d.x))
          return d.x
        })
        .attr('cy', (d: any) => {
          d.y = Math.max(R, Math.min(height - R, d.y))
          return d.y
        })

      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      label
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y)

      edgeLabel
        .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
        .attr('y', (d: any) => (d.source.y + d.target.y) / 2 - 8)
    })
}

// 图谱数据变化时自动重绘
watch(graphResult, () => {
  nextTick(() => initD3Graph())
})

// ============================================================
// 5. 筛选联动 & API 调用
// ============================================================

/** 从 selectedFilters 构造 QueryFilters（空数组转为 undefined 表示不过滤） */
function currentFilters(): QueryFilters {
  return {
    years: selectedFilters.tournamentYears.length ? selectedFilters.tournamentYears : undefined,
    team_ids: selectedFilters.teamIds.length ? selectedFilters.teamIds : undefined,
    stages: selectedFilters.stages.length ? selectedFilters.stages : undefined,
    result_types: selectedFilters.resultTypes.length ? selectedFilters.resultTypes : undefined,
    has_penalties: selectedFilters.hasPenalties ? true : undefined,
  }
}

/** 并行请求 matches + graph */
async function loadMatchesAndGraph() {
  const f = currentFilters()
  const [mRes, gRes] = await Promise.all([
    fetchMatches(f),
    fetchGraph(f),
  ])
  if (mRes) {
    allMatches.value = mRes.items
  }
  if (gRes) {
    graphResult.value = gRes
  }
}

// 筛选条件变化 → 重新加载时间线和图谱
watch(
  () => [
    selectedFilters.tournamentYears.length,
    selectedFilters.teamIds.join(','),
    selectedFilters.stages.join(','),
    selectedFilters.resultTypes.join(','),
    selectedFilters.hasPenalties,
  ],
  () => loadMatchesAndGraph(),
)

// ============================================================
// 6. 页面初始化
// ============================================================
onMounted(async () => {
  const [fo] = await Promise.all([
    fetchFilterOptions(),
    loadMatchesAndGraph(),
  ])
  if (fo) {
    filterOptions.value = fo
  }
})
</script>

<style scoped>
/* ============================================================
   根布局：Flexbox 行 —— 左侧固定 + 右侧自适应，彻底消除重叠
   ============================================================ */
.app-layout {
  display: flex;
  height: 100vh;
  background: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  overflow: hidden;
}

/* ---- 左侧筛选栏：300px 固定，独立滚动 ---- */
.sidebar {
  width: 300px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #fff;
  border-right: 1px solid #e0e0e0;
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 2;
}

.sidebar-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  border-bottom: 2px solid #4a90d9;
  padding-bottom: 8px;
}

.filter-block {
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 4px;
}

.filter-block-header {
  display: flex;
  justify-content: space-between;
  padding: 6px 4px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #555;
  border-radius: 4px;
  user-select: none;
}
.filter-block-header:hover { background: #f5f7fa; }

.filter-arrow { font-size: 11px; color: #999; }

.filter-checks {
  display: flex;
  flex-direction: column;
  padding: 2px 4px;
}

.filter-checks-scroll {
  max-height: 200px;
  overflow-y: auto;
}

.filter-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #444;
}
.filter-check:hover { background: #f5f7fa; }
.filter-check input { width: 15px; height: 15px; accent-color: #4a90d9; flex-shrink: 0; cursor: pointer; }

.filter-actions {
  display: flex;
  gap: 6px;
  padding: 4px 6px;
}
.filter-actions button {
  flex: 1;
  padding: 3px 0;
  font-size: 11px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  background: #fafafa;
  color: #666;
  cursor: pointer;
}
.filter-actions button:hover { background: #eef; color: #4a90d9; border-color: #4a90d9; }

.sidebar-reset {
  margin-top: 8px;
  padding: 10px 0;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #f5f5f5;
  color: #555;
  font-size: 14px;
  cursor: pointer;
  position: sticky;
  bottom: 0;
}
.sidebar-reset:hover { background: #e8e8e8; }

/* ---- 右侧主内容区：flex:1 纵向 flex，禁止外层滚动 ---- */
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
   上半部分：问答 + D3 图 —— 占据剩余高度
   ============================================================ */
.top-row {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 16px;
}

/* ---- 问答区：flex 列，输入框强制触底 ---- */
.qa-section {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* 可滚动内容：提问条 + Badge + 表格 + 来源 */
.qa-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 用户提问展示条 */
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

.question-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.question-label {
  font-weight: 700;
  color: #888;
  flex-shrink: 0;
}

.question-text {
  color: #1a1a1a;
  font-weight: 500;
}

/* 意图 Badge 行 */
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

.badge-label {
  font-size: 13px;
  font-weight: 700;
  color: #888;
  margin-right: 4px;
}

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
.badge-val { }

.badge-blue  { background: #e8f0fe; color: #1a56c4; }
.badge-green { background: #e6f7e6; color: #1a7a2e; }
.badge-orange{ background: #fef3e5; color: #b85c10; }
.badge-purple{ background: #f3e8ff; color: #6b21a8; }

/* 事实面板 */
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

.fact-table {
  width: 100%;
  border-collapse: collapse;
}

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

.fact-value {
  color: #1a1a1a;
  font-weight: 500;
}

.champion-crown { margin-right: 4px; }

/* 来源面板 */
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

.source-card-url {
  color: #4a90d9;
  text-decoration: none;
}
.source-card-url:hover { text-decoration: underline; }

/* 输入栏：始终贴合问答区底部 */
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
.qa-send-btn:hover { background: #357abd; }

/* ---- 图谱 ---- */
.graph-section {
  width: 280px;
  min-width: 280px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.d3-box {
  width: 100%;
  height: 280px;
  background: #fafbfc;
  border: 1px solid #eee;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.d3-svg { width: 100%; height: 280px; }
.d3-svg text { text-shadow: 1px 1px 2px #fff, -1px -1px 2px #fff; }

.graph-legend {
  margin-top: 12px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 12px;
}

.graph-legend h5 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 700;
  color: #555;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  color: #666;
}

.leg-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  background: #4a90d9;
  border-radius: 50%;
  flex-shrink: 0;
}

.leg-line {
  display: inline-block;
  width: 20px;
  height: 2px;
  background: #999;
  flex-shrink: 0;
}

.leg-arrow {
  flex-shrink: 0;
  color: #999;
}

.legend-fmt {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.legend-fmt p {
  margin: 0 0 4px 0;
  color: #888;
}

.legend-fmt code {
  display: block;
  font-size: 11px;
  color: #4a90d9;
  background: #e8f0fe;
  padding: 3px 6px;
  border-radius: 4px;
  word-break: break-all;
}

/* ============================================================
   下半部分：横向时间线
   ============================================================ */
.timeline-section {
  flex-shrink: 0;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  overflow-y: auto;
}

.tl-scroll {
  overflow-x: auto;
  overflow-y: visible;
  padding-bottom: 4px;
}

.tl-track {
  display: flex;
  align-items: flex-start;
  gap: 0;
  position: relative;
  padding: 26px 20px 12px 20px;
  min-width: min-content;
}

.tl-spine {
  position: absolute;
  top: 26px;
  left: 20px;
  right: 20px;
  height: 2px;
  background: #c8cdd4;
  border-radius: 1px;
  z-index: 0;
}

.tl-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  z-index: 1;
  flex-shrink: 0;
}

.tl-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding-top: 19px;
}

.tl-dot {
  width: 14px;
  height: 14px;
  background: #4a90d9;
  border: 2px solid #fff;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  position: relative;
  z-index: 2;
}

.tl-stage-name {
  font-size: 11px;
  font-weight: 600;
  color: #4a90d9;
  white-space: nowrap;
  margin-top: 2px;
}

.tl-stage-conn {
  width: 2px;
  height: 14px;
  background: #ccc;
  border-radius: 1px;
  flex-shrink: 0;
}

.tl-cards {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.tl-match {
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s;
  min-width: 150px;
}

.tl-match:hover { transform: translateY(-1px); }

.tl-active .tl-card {
  border-color: #4a90d9;
  box-shadow: 0 0 0 2px rgba(74,144,217,0.2);
}

.tl-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  white-space: nowrap;
  transition: border-color 0.12s, box-shadow 0.12s;
}

.tl-teams {
  font-size: 12px;
  font-weight: 600;
  color: #333;
}

.tl-score {
  font-size: 11px;
  color: #888;
  font-weight: 500;
}

.tl-pk {
  font-size: 10px;
  color: #b85c10;
}

/* ==== 展开详情面板 ==== */
.tl-detail {
  margin-top: 20px;
  margin-bottom: 24px;
  background: #f5f9ff;
  border: 1px solid #d0ddf0;
  border-radius: 8px;
  padding: 20px;
}

.tl-detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.tl-detail-head h4 {
  margin: 0;
  font-size: 16px;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tl-vs {
  font-weight: 400;
  color: #999;
  font-size: 13px;
}

.tl-tag {
  font-size: 11px;
  font-weight: 600;
  color: #4a90d9;
  background: #e8f0fe;
  padding: 2px 8px;
  border-radius: 4px;
}

.tl-tag-year {
  background: #fef3e5;
  color: #b85c10;
}

.tl-detail-head button {
  padding: 6px 14px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  flex-shrink: 0;
}
.tl-detail-head button:hover { background: #f5f5f5; }

.tl-detail-body {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

.tl-score-card {
  flex: 1;
  min-width: 190px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 14px;
}

.tl-score-card h5 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #333;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 8px;
}

.tl-score-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.tl-team-name {
  font-size: 14px;
  font-weight: 600;
  color: #555;
}

.tl-big-score {
  font-size: 28px;
  font-weight: 800;
  color: #1a1a1a;
}

.tl-colon {
  font-size: 22px;
  font-weight: 300;
  color: #bbb;
}

.tl-na {
  margin: 8px 0 0 0;
  font-size: 12px;
  color: #aaa;
  text-align: center;
}

.tl-summary {
  margin: 8px 0 0 0;
  font-size: 12px;
  color: #888;
  text-align: center;
  font-weight: 500;
}

.tl-src-card {
  min-width: 240px;
}

.tl-src-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.tl-src-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #555;
  margin-bottom: 4px;
}

.tl-src-id {
  font-weight: 700;
  color: #4a90d9;
  flex-shrink: 0;
}

/* ============================================================
   全局滚动条美化
   ============================================================ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #c8cdd4; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #a0a7b0; }
::-webkit-scrollbar-corner { background: transparent; }
</style>
