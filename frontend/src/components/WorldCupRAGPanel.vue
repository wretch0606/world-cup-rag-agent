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
          <label v-for="y in filterOptions.tournaments" :key="y" class="filter-check">
            <input type="checkbox" :value="y" v-model="selectedFilters.tournamentYears" />
            <span>{{ y }}</span>
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
          <label v-for="t in filterOptions.teams" :key="t.id" class="filter-check">
            <input type="checkbox" :value="t.id" v-model="selectedFilters.teamIds" />
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
          <label v-for="r in filterOptions.resultTypes" :key="r.value" class="filter-check">
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

            <!-- 意图标签 Badge 行 -->
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

            <!-- 核心事实表：6 行纵向结构 -->
            <div class="fact-panel">
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

            <!-- 引用来源卡片 -->
            <div class="sources-panel">
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
import { ref, reactive, computed, onMounted } from 'vue'
import * as d3 from 'd3'

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

const filterOptions = {
  tournaments: [1994, 2006, 2010, 2014, 2018, 2022],
  teams: [
    { id: 'team_ARG', name: '阿根廷' },{ id: 'team_FRA', name: '法国' },{ id: 'team_CRO', name: '克罗地亚' },
    { id: 'team_GER', name: '德国' },{ id: 'team_ESP', name: '西班牙' },{ id: 'team_NED', name: '荷兰' },
    { id: 'team_BRA', name: '巴西' },{ id: 'team_ITA', name: '意大利' },{ id: 'team_ENG', name: '英格兰' },
    { id: 'team_BEL', name: '比利时' },{ id: 'team_URU', name: '乌拉圭' },{ id: 'team_POR', name: '葡萄牙' },
    { id: 'team_MAR', name: '摩洛哥' },{ id: 'team_AUS', name: '澳大利亚' },{ id: 'team_DEN', name: '丹麦' },
    { id: 'team_RUS', name: '俄罗斯' },{ id: 'team_PAR', name: '巴拉圭' },{ id: 'team_ALG', name: '阿尔及利亚' },
  ],
  stages: [
    { value: 'group', label: '小组赛' },{ value: 'round_of_16', label: '1/8 决赛' },
    { value: 'quarter_final', label: '1/4 决赛' },{ value: 'semi_final', label: '半决赛' },
    { value: 'third_place', label: '三四名决赛' },{ value: 'final', label: '决赛' },
  ],
  resultTypes: [
    { value: 'regulation', label: '常规时间' },{ value: 'extra_time', label: '加时赛' },
    { value: 'penalties', label: '点球大战' },{ value: 'draw', label: '平局' },
  ],
}

const selectedFilters = reactive({
  tournamentYears: [] as number[],
  teamIds: [] as string[],
  stages: [] as string[],
  resultTypes: [] as string[],
  hasPenalties: false,
})

function selectAllTournaments() { selectedFilters.tournamentYears = [...filterOptions.tournaments] }
function clearAllTournaments() { selectedFilters.tournamentYears = [] }
function selectAllTeams() { selectedFilters.teamIds = filterOptions.teams.map(t => t.id) }
function clearAllTeams() { selectedFilters.teamIds = [] }
function selectAllStages() { selectedFilters.stages = filterOptions.stages.map(s => s.value) }
function clearAllStages() { selectedFilters.stages = [] }
function resetFilters() {
  selectedFilters.tournamentYears = []; selectedFilters.teamIds = []
  selectedFilters.stages = []; selectedFilters.resultTypes = []; selectedFilters.hasPenalties = false
}

// ============================================================
// 2. API 数据模型 & 意图 Badge + 事实表
// ============================================================

// ---- 新接口契约 (v2 — 结构化 score 对象) ----
interface TeamRef { team_id: string; name: string }
interface ScoreDetail { home: number; away: number }
interface MatchScore {
  regular_time: ScoreDetail
  after_extra_time: ScoreDetail | null
  penalties: ScoreDetail | null
  display: string
  penalty_display: string | null
}
interface ApiFact {
  fact_id: string; match_id: string; stage_name: string
  home_team: TeamRef; away_team: TeamRef
  score: MatchScore; winner_team: TeamRef | null
}
interface ApiSourceItem {
  source_id: string; title: string; url: string | null
}
interface ApiGraphNode { id: string; name: string; type: string }
interface ApiGraphEdge { id: string; source: string; target: string; match_id: string; label: string }
interface ApiResponseData {
  status: string; intent: string; route: string; answer: string
  facts: ApiFact[]; sources: ApiSourceItem[]
  graph: { nodes: ApiGraphNode[]; edges: ApiGraphEdge[] }
}
interface ApiEnvelope { success: boolean; code: string; message: string; data: ApiResponseData }

// ---- Mock API 响应 (v2 契约) ----
const apiResponse: ApiEnvelope = {
  success: true, code: 'OK', message: '查询成功',
  data: {
    status: 'ok', intent: 'match_result_query', route: 'structured_query',
    answer: '2022年世界杯决赛，阿根廷与法国加时赛后3:3战平，阿根廷在点球大战中4:2获胜并夺冠。',
    facts: [{
      fact_id: 'fact-M-2022-64-result', match_id: 'M-2022-64', stage_name: '决赛',
      home_team: { team_id: 'team_ARG', name: '阿根廷' },
      away_team: { team_id: 'team_FRA', name: '法国' },
      score: {
        regular_time: { home: 2, away: 2 },
        after_extra_time: { home: 3, away: 3 },
        penalties: { home: 4, away: 2 },
        display: '3:3', penalty_display: '4:2',
      },
      winner_team: { team_id: 'team_ARG', name: '阿根廷' },
    }],
    sources: [
      { source_id: 'source-example-001', title: 'FIFA World Cup 2022 — Official Match Report', url: 'https://example.com' },
      { source_id: 'source-example-002', title: 'FIFA World Cup 2018 — Official Match Report', url: 'https://example.com/2018' },
    ],
    graph: {
      nodes: [
        { id: 'team_ARG', name: '阿根廷', type: 'team' },
        { id: 'team_FRA', name: '法国', type: 'team' },
        { id: 'team_CRO', name: '克罗地亚', type: 'team' },
        { id: 'team_GER', name: '德国', type: 'team' },
        { id: 'team_NED', name: '荷兰', type: 'team' },
        { id: 'team_ITA', name: '意大利', type: 'team' },
      ],
      edges: [
        { id: 'edge-M-2022-64', source: 'team_ARG', target: 'team_FRA', match_id: 'M-2022-64', label: '2022·决赛·3:3（点球4:2）' },
        { id: 'edge-M-2022-61', source: 'team_ARG', target: 'team_CRO', match_id: 'M-2022-61', label: '2022·半决赛·3:0' },
        { id: 'edge-M-2022-57', source: 'team_ARG', target: 'team_NED', match_id: 'M-2022-57', label: '2022·1/4决赛·2:2（点球4:3）' },
        { id: 'edge-M-2018-64', source: 'team_FRA', target: 'team_CRO', match_id: 'M-2018-64', label: '2018·决赛·4:2' },
        { id: 'edge-M-2014-64', source: 'team_GER', target: 'team_ARG', match_id: 'M-2014-64', label: '2014·决赛·1:0' },
        { id: 'edge-M-2006-64', source: 'team_ITA', target: 'team_FRA', match_id: 'M-2006-64', label: '2006·决赛·1:1（点球5:3）' },
      ],
    },
  },
}

const intentLabels = { title: '分析结果' }

// ---- 问答输入 ----
const qaLabels = {
  questionPrefix: '问：',
  inputPlaceholder: '请输入您的问题...',
  sendBtn: '发送',
}

const userInputText = ref('')
const currentUserQuestion = ref('2022年世界杯决赛阿根廷对法国的比分是多少？')

function handleSendQuestion() {
  const trimmed = userInputText.value.trim()
  if (!trimmed) return
  currentUserQuestion.value = trimmed
  userInputText.value = ''
}

// 从 API 响应动态生成 Badge
const intentBadges = computed(() => {
  const d = apiResponse.data
  const f = d.facts[0]
  const teams = f ? `${f.home_team.name}, ${f.away_team.name}` : '—'
  return [
    { key: '意图',   val: d.intent === 'match_result_query' ? '精确事实查询' : d.intent, css: 'badge-blue' },
    { key: '实体',   val: teams, css: 'badge-green' },
    { key: '赛事',   val: f ? `2022·${f.stage_name}` : '—', css: 'badge-orange' },
    { key: '置信度', val: '99%', css: 'badge-purple' },
  ]
})

const factLabels = { title: '核心事实' }

interface FactRow { label: string; value: string }

const factRows = computed<FactRow[]>(() => {
  const f = apiResponse.data.facts[0]
  if (!f) return []
  const s = f.score
  return [
    { label: '赛事',     value: `2022 世界杯 · ${f.stage_name}` },
    { label: '对阵',     value: `${f.home_team.name} vs ${f.away_team.name}` },
    { label: '常规时间', value: `${f.home_team.name} ${s.regular_time.home} : ${s.regular_time.away} ${f.away_team.name}` },
    { label: '加时赛',   value: s.after_extra_time ? `${f.home_team.name} ${s.after_extra_time.home} : ${s.after_extra_time.away} ${f.away_team.name}` : '（无加时）' },
    { label: '点球',     value: s.penalty_display ? `${f.home_team.name} ${s.penalty_display} ${f.away_team.name}` : '（无点球大战）' },
    { label: '冠军',     value: f.winner_team ? f.winner_team.name : '—' },
  ]
})

// ============================================================
// 3. 来源卡片 — 来自 API response.data.sources
// ============================================================
const sourceLabels = { title: '引用来源' }

const sourceCatalog = computed<ApiSourceItem[]>(() => apiResponse.data.sources)

// ============================================================
// 4. D3 图 —— 数据来自 API response.data.graph
// ============================================================
const graphLabels = {
  title: '球队关系图谱', legendTitle: '图例说明',
  nodeDesc: '节点 = 球队实体', edgeDesc: '连线 = 比赛（有向边）', arrowDesc: '方向 = 胜方 → 败方',
  edgeFormatDesc: '连线标签格式：', edgeFormatExample: '2022·决赛·3:3（点球4:2）',
}

const graphData = reactive({
  nodes: [...apiResponse.data.graph.nodes] as ApiGraphNode[],
  edges: [...apiResponse.data.graph.edges] as ApiGraphEdge[],
})

function initD3Graph() {
  const el = document.getElementById('d3-graph-container')
  if (!el) return

  const width = 400, height = 280
  const colors = ['#4A90D9', '#E07B39', '#5D9C6E', '#C0504D', '#8064A2', '#F2A640']

  // 深拷贝 + 注入 D3 力仿真所需字段
  const nodes: any[] = graphData.nodes.map(n => ({ ...n }))
  const edges: any[] = graphData.edges.map(e => ({ ...e }))

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
    .data(edges)
    .join('line')
    .attr('stroke', '#999')
    .attr('stroke-width', 1.6)
    .attr('marker-end', 'url(#ah)')

  // 节点圆
  const node = svg.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', 26)
    .attr('fill', (_d: any, i: number) => colors[i % 6])
    .attr('opacity', 0.88)
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  // 节点标签
  const label = svg.append('g')
    .selectAll('text')
    .data(nodes)
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
    .data(edges)
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
  d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(200))
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

// ============================================================
// 5. 时间线 — 使用结构化 score 对象
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
  score: MatchScore
  sources: TSource[]
}
interface TStage { stage: string; stage_name: string; matches: TMatch[] }

function mkScore(regH: number, regA: number, etH: number|null, etA: number|null, pkH: number|null, pkA: number|null, display: string, pkDisplay: string|null): MatchScore {
  return {
    regular_time: { home: regH, away: regA },
    after_extra_time: etH !== null && etA !== null ? { home: etH, away: etA } : null,
    penalties: pkH !== null && pkA !== null ? { home: pkH, away: pkA } : null,
    display,
    penalty_display: pkDisplay,
  }
}

const timelineStages: TStage[] = [
  { stage:'round_of_16', stage_name:'1/8 决赛', matches:[
    { match_id:'M-2022-49', match_date:'2022-12-03', tournament_year:2022, stage:'round_of_16', stage_name:'1/8 决赛', home_team_name:'荷兰', away_team_name:'美国', score: mkScore(3,1,null,null,null,null,'3:1',null), sources:[{ source_id:'source-001', title:'FIFA R16 Report', url:null }] },
    { match_id:'M-2022-50', match_date:'2022-12-03', tournament_year:2022, stage:'round_of_16', stage_name:'1/8 决赛', home_team_name:'阿根廷', away_team_name:'澳大利亚', score: mkScore(2,1,null,null,null,null,'2:1',null), sources:[{ source_id:'source-001', title:'FIFA R16 Report', url:null }] },
  ]},
  { stage:'quarter_final', stage_name:'1/4 决赛', matches:[
    { match_id:'M-2022-57', match_date:'2022-12-09', tournament_year:2022, stage:'quarter_final', stage_name:'1/4 决赛', home_team_name:'荷兰', away_team_name:'阿根廷', score: mkScore(2,2,2,2,3,4,'2:2','3:4'), sources:[{ source_id:'source-001', title:'FIFA QF Report', url:'https://fifa.com/qf' }] },
    { match_id:'M-2022-60', match_date:'2022-12-10', tournament_year:2022, stage:'quarter_final', stage_name:'1/4 决赛', home_team_name:'英格兰', away_team_name:'法国', score: mkScore(1,2,null,null,null,null,'1:2',null), sources:[{ source_id:'source-001', title:'FIFA QF Report', url:null }] },
  ]},
  { stage:'semi_final', stage_name:'半决赛', matches:[
    { match_id:'M-2022-61', match_date:'2022-12-13', tournament_year:2022, stage:'semi_final', stage_name:'半决赛', home_team_name:'阿根廷', away_team_name:'克罗地亚', score: mkScore(3,0,null,null,null,null,'3:0',null), sources:[{ source_id:'source-001', title:'FIFA SF Report', url:null }] },
    { match_id:'M-2022-62', match_date:'2022-12-14', tournament_year:2022, stage:'semi_final', stage_name:'半决赛', home_team_name:'法国', away_team_name:'摩洛哥', score: mkScore(2,0,null,null,null,null,'2:0',null), sources:[{ source_id:'source-001', title:'FIFA SF Report', url:null }] },
  ]},
  { stage:'third_place', stage_name:'三四名决赛', matches:[
    { match_id:'M-2022-63', match_date:'2022-12-17', tournament_year:2022, stage:'third_place', stage_name:'三四名决赛', home_team_name:'克罗地亚', away_team_name:'摩洛哥', score: mkScore(2,1,null,null,null,null,'2:1',null), sources:[{ source_id:'source-001', title:'FIFA 3rd Report', url:null }] },
  ]},
  { stage:'final', stage_name:'决赛', matches:[
    { match_id:'M-2022-64', match_date:'2022-12-18', tournament_year:2022, stage:'final', stage_name:'决赛', home_team_name:'阿根廷', away_team_name:'法国', score: mkScore(2,2,3,3,4,2,'3:3','4:2'), sources:[{ source_id:'source-001', title:'FIFA World Cup 2022 Final Report', url:'https://www.fifa.com/worldcup/final' }] },
  ]},
]

const expandedMatchId = ref<string | null>(null)

function findTMatch(id: string): TMatch | null {
  for (const s of timelineStages) { const f = s.matches.find(m => m.match_id === id); if (f) return f }
  return null
}
const expandedMatchDetail = computed<TMatch | null>(() => expandedMatchId.value ? findTMatch(expandedMatchId.value) : null)
function toggleMatchDetail(id: string) { expandedMatchId.value = expandedMatchId.value === id ? null : id }
function closeMatchDetail() { expandedMatchId.value = null }

onMounted(() => { initD3Graph() })
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
  padding: 10px 12px;
  border-bottom: 1px solid #f2f2f2;
  font-size: 14px;
}

.fact-label {
  font-weight: 700;
  color: #555;
  white-space: nowrap;
  width: 100px;
  background: #fafbfc;
  border-right: 1px solid #f0f0f0;
}

.fact-value {
  color: #1a1a1a;
  font-weight: 500;
}

.champion-crown {
  margin-right: 6px;
  font-size: 16px;
}

/* 来源卡片 */
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
  background: #fafbfc;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 12px 14px;
}

.source-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.source-card-id {
  font-weight: 700;
  color: #4a90d9;
  font-family: monospace;
  font-size: 13px;
}

.source-card-version {
  font-size: 11px;
  color: #aaa;
  font-family: monospace;
}

.source-card-title {
  margin: 4px 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.source-card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #888;
  margin-top: 6px;
}

.source-card-url { color: #4a90d9; text-decoration: none; }
.source-card-url:hover { text-decoration: underline; }
.source-card-page { color: #888; }
.source-card-doc { color: #aaa; }

/* 底部提问输入框：margin-top:auto 强制沉底 */
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
  padding: 10px 14px;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  color: #333;
  background: #fafbfc;
  transition: border-color 0.2s;
}

.qa-input:focus {
  border-color: #4a90d9;
  box-shadow: 0 0 0 2px rgba(74,144,217,.12);
}

.qa-send-btn {
  padding: 10px 22px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}

.qa-send-btn:hover {
  background: #3a7bc8;
}

/* ---- D3 图：固定 400px ---- */
.graph-section {
  width: 400px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.d3-box {
  width: 100%;
  min-height: 280px;
  border: 1px dashed #ccc;
  border-radius: 6px;
  background: #fafbfc;
  overflow: hidden;
  flex-shrink: 0;
}

.d3-svg { width:100%; height:280px; }

/* SVG 连线文字防穿透阴影 */
.d3-svg text { text-shadow: 1px 1px 2px #fff, -1px -1px 2px #fff; }

.graph-legend {
  background: #f9fafb;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 10px 12px;
}
.graph-legend h5 { margin:0 0 6px; font-size:13px; color:#555; }
.legend-row { display:flex; align-items:center; gap:8px; font-size:12px; color:#666; margin:4px 0; }
.leg-dot { width:12px; height:12px; border-radius:50%; background:#4a90d9; display:inline-block; flex-shrink:0; }
.leg-line { width:18px; height:2px; background:#999; display:inline-block; flex-shrink:0; }
.leg-arrow { color:#999; font-size:14px; width:18px; text-align:center; flex-shrink:0; }
.legend-fmt { border-top:1px solid #eee; padding-top:6px; margin-top:4px; }
.legend-fmt p { margin:0 0 2px; font-size:11px; color:#999; }
.legend-fmt code { font-size:12px; background:#eef; padding:2px 6px; border-radius:3px; color:#4a90d9; }

/* ============================================================
   底部时间线：min-height 保底，overflow-y:auto 防裁切
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
  flex-shrink: 0;
  overflow-x: auto;
  padding: 12px 0 8px;
}

.tl-track {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  min-width: max-content;
  padding: 0 16px 12px;
  position: relative;
}

.tl-spine {
  position: absolute;
  top: 26px;                    /* dot 圆心位置 */
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #4a90d9, #5d9c6e, #e07b39, #c0504d, #27ae60);
  border-radius: 2px;
  z-index: 0;
}

/* ---- 阶段分组：flex 列，垂直居中对齐，保证卡片在圆圈正下方 ---- */
.tl-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  z-index: 1;
  flex-shrink: 0;
}

/* 阶段标记：dot 圆心对准脊柱 (padding-top = 26 - 14/2 = 19) */
.tl-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding-top: 19px;
}

.tl-dot {
  width: 14px; height: 14px;
  border-radius: 50%;
  background: #4a90d9;
  border: 3px solid #fff;
  box-shadow: 0 0 0 2px #4a90d9;
  flex-shrink: 0;
}

.tl-stage-name {
  font-size: 11px;
  font-weight: 700;
  color: #444;
  white-space: nowrap;
}

/* 圆圈 → 卡片 的连接竖线 */
.tl-stage-conn {
  width: 2px;
  height: 14px;
  background: #ccc;
  border-radius: 1px;
  flex-shrink: 0;
}

/* 比赛卡片垂直罗列 */
.tl-cards {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

/* 比赛节点 */
.tl-match {
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s;
}
.tl-match:hover { transform: scale(1.04); }

.tl-card {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 6px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
  min-width: 150px;
  text-align: center;
}
.tl-active .tl-card {
  border-color: #4a90d9;
  box-shadow: 0 2px 10px rgba(74,144,217,.22);
  background: #f0f6ff;
}

.tl-teams { font-size: 13px; font-weight: 600; color: #333; }
.tl-score { font-size: 15px; font-weight: 700; color: #1a1a1a; font-family: 'Fira Code', monospace; }
.tl-pk { font-size: 11px; color: #e07b39; }

/* 展开面板 */
.tl-detail {
  margin-top: 20px;
  margin-bottom: 24px;
  border: 2px solid #4a90d9;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  animation: tlIn .25s ease-out;
}
@keyframes tlIn { from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:translateY(0)} }

.tl-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: linear-gradient(135deg, #e8f0fe, #f5f7fa);
  border-bottom: 1px solid #d0ddf0;
}
.tl-detail-head h4 { margin:0; font-size:16px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.tl-vs { font-weight:400; color:#888; font-size:13px; }
.tl-tag { font-size:12px; background:#4a90d9; color:#fff; padding:2px 10px; border-radius:12px; font-weight:600; }
.tl-tag-year { background:#f0f0f0; color:#666; }
.tl-detail-head button {
  padding:6px 14px; border:1px solid #d0d0d0; border-radius:6px; background:#fff; color:#888; font-size:13px; cursor:pointer;
}
.tl-detail-head button:hover { background:#f5f5f5; color:#333; }

.tl-detail-body {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
  padding: 20px;
}

.tl-score-card {
  background: #fafbfc;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 14px 16px;
}
.tl-score-card h5 { margin:0 0 8px; font-size:13px; color:#555; border-bottom:1px solid #eee; padding-bottom:6px; }

.tl-score-row {
  display: flex; align-items: center; justify-content: center; gap: 8px; padding: 4px 0;
}
.tl-team-name { font-size:14px; font-weight:600; color:#333; min-width:40px; }
.tl-team-name:first-child { text-align:right; }
.tl-team-name:last-child { text-align:left; }
.tl-big-score { font-size:26px; font-weight:800; color:#1a1a1a; font-family:'Fira Code',monospace; }
.tl-colon { font-size:18px; color:#999; font-weight:700; }
.tl-na { margin:4px 0 0; font-size:12px; color:#bbb; font-style:italic; text-align:center; }
.tl-summary { margin:6px 0 0; font-size:12px; color:#888; text-align:center; background:#fff; padding:5px 10px; border-radius:4px; border:1px dashed #ddd; }

.tl-src-card { grid-column: 1 / -1; }
.tl-src-list { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:5px; }
.tl-src-item { font-size:12px; color:#555; display:flex; align-items:baseline; gap:6px; padding:5px 10px; background:#fff; border-radius:4px; border:1px solid #f0f0f0; flex-wrap:wrap; }
.tl-src-id { font-weight:700; color:#4a90d9; font-family:monospace; }

/* ============================================================
   响应式
   ============================================================ */
@media (max-width: 1100px) {
  .app-layout { flex-direction: column; }
  .sidebar { width: 100%; flex-shrink: 1; max-height: 260px; border-right: none; border-bottom: 1px solid #e0e0e0; }
  .main-area { padding: 12px; }
  .top-row { flex-direction: column; }
  .graph-section { width: 100%; }
}

/* ============================================================
   全局滚动条美化
   ============================================================ */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb {
  background: #c8cdd4;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #a0a7b0;
}
::-webkit-scrollbar-corner {
  background: transparent;
}
</style>
