<template>
  <section class="timeline-section">
    <div class="tl-header-bar">
      <h3 class="panel-title">{{ labels.title }}</h3>
      <span v-if="!loading && !error && total > 0" class="tl-total-badge">共 {{ total }} 场</span>
    </div>

    <!-- ====== 加载态 ====== -->
    <div v-if="loading" class="tl-state">
      <div class="tl-skeleton-grid">
        <div v-for="i in 6" :key="i" class="tl-skeleton-card"></div>
      </div>
    </div>

    <!-- ====== 错误态 ====== -->
    <div v-else-if="error" class="tl-state tl-error">
      <span class="tl-error-icon">⚠️</span>
      <p>{{ labels.loadError }}</p>
      <button class="tl-retry-btn" @click="fetchPage(page)">{{ labels.retry }}</button>
    </div>

    <!-- ====== 空态 ====== -->
    <div v-else-if="!matches.length" class="tl-state tl-empty">
      <span class="tl-empty-icon">📅</span>
      <p>{{ labels.empty }}</p>
    </div>

    <!-- ====== 数据态 ====== -->
    <template v-else>
      <!-- 翻页控件（顶部） -->
      <PaginationBar
        :page="page"
        :total-pages="totalPages"
        :total="total"
        :labels="labels"
        @prev="goPrev"
        @next="goNext"
      />

      <!-- 按阶段分组 → CSS Grid -->
      <div class="tl-stage-list">
        <div v-for="stage in stageGroups" :key="stage.stage" class="tl-stage-section">
          <div class="tl-stage-header">
            <span class="tl-stage-dot"></span>
            <h4 class="tl-stage-name">{{ stage.stage_name }}</h4>
            <span class="tl-stage-count">{{ stage.matches.length }} 场</span>
          </div>

          <div class="tl-match-grid">
            <div
              v-for="m in stage.matches"
              :key="m.match_id"
              :class="['tl-match-card', { 'tl-card-active': expandedMatchId === m.match_id }]"
              @click="toggleDetail(m.match_id)"
            >
              <div class="tl-card-teams">
                <span class="tl-card-home">{{ m.home_team_name }}</span>
                <span class="tl-card-vs">vs</span>
                <span class="tl-card-away">{{ m.away_team_name }}</span>
              </div>
              <div class="tl-card-score">
                <span class="tl-card-score-main">{{ m.score.display }}</span>
                <span v-if="m.score.penalty_display" class="tl-card-pk">({{ m.score.penalty_display }})</span>
              </div>
              <div class="tl-card-meta">
                <span class="tl-card-year">{{ m.tournament_year }}</span>
                <span v-if="m.match_date" class="tl-card-date">{{ m.match_date }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 翻页控件（底部） -->
      <PaginationBar
        :page="page"
        :total-pages="totalPages"
        :total="total"
        :labels="labels"
        @prev="goPrev"
        @next="goNext"
      />
    </template>

    <!-- ====== 展开的比分明细 ====== -->
    <div v-if="expandedMatchDetail" class="tl-detail">
      <div class="tl-detail-head">
        <h4>
          {{ expandedMatchDetail.home_team_name }}
          <span class="tl-vs">vs</span>
          {{ expandedMatchDetail.away_team_name }}
          <span class="tl-tag">{{ expandedMatchDetail.stage_name }}</span>
          <span class="tl-tag tl-tag-year">{{ expandedMatchDetail.tournament_year }}</span>
        </h4>
        <button @click="closeDetail">{{ labels.close }}</button>
      </div>

      <div class="tl-detail-body">
        <!-- 90 分钟 -->
        <div class="tl-score-card">
          <h5>{{ labels.regularTime }}</h5>
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
          <h5>{{ labels.extraTime }}</h5>
          <div class="tl-score-row">
            <span class="tl-team-name">{{ expandedMatchDetail.home_team_name }}</span>
            <span class="tl-big-score">{{ expandedMatchDetail.score.after_extra_time?.home ?? '—' }}</span>
            <span class="tl-colon">:</span>
            <span class="tl-big-score">{{ expandedMatchDetail.score.after_extra_time?.away ?? '—' }}</span>
            <span class="tl-team-name">{{ expandedMatchDetail.away_team_name }}</span>
          </div>
          <p v-if="!expandedMatchDetail.score.after_extra_time" class="tl-na">{{ labels.notApplicable }}</p>
          <p v-else class="tl-summary">{{ labels.formalScore }}{{ expandedMatchDetail.score.display }}</p>
        </div>

        <!-- 点球大战 -->
        <div class="tl-score-card">
          <h5>{{ labels.penaltyShootout }}</h5>
          <div class="tl-score-row">
            <span class="tl-team-name">{{ expandedMatchDetail.home_team_name }}</span>
            <span class="tl-big-score">{{ expandedMatchDetail.score.penalties?.home ?? '—' }}</span>
            <span class="tl-colon">:</span>
            <span class="tl-big-score">{{ expandedMatchDetail.score.penalties?.away ?? '—' }}</span>
            <span class="tl-team-name">{{ expandedMatchDetail.away_team_name }}</span>
          </div>
          <p v-if="!expandedMatchDetail.score.penalties" class="tl-na">{{ labels.notApplicable }}</p>
          <p v-else class="tl-summary">{{ labels.penaltyScoreLabel }}{{ expandedMatchDetail.score.penalty_display }}</p>
        </div>

        <!-- 来源 -->
        <div class="tl-score-card tl-src-card">
          <h5>{{ labels.sourceDetails }}</h5>
          <ul v-if="expandedMatchDetail.sources.length" class="tl-src-list">
            <li v-for="s in expandedMatchDetail.sources" :key="s.source_id" class="tl-src-item">
              <span class="tl-src-id">[{{ s.source_id }}]</span>
              <span>{{ s.title }}</span>
              <a v-if="s.url" :href="s.url" target="_blank" rel="noopener">🔗</a>
            </li>
          </ul>
          <p v-else class="tl-na">{{ labels.noSource }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { QueryFilters, MatchItem, MatchSourceItem } from '@/api'
import { fetchMatches } from '@/api'

// ============================================================
// Props
// ============================================================
const props = defineProps<{
  filters: QueryFilters
}>()

// ============================================================
// 文案
// ============================================================
const labels = {
  title: '比赛时间线',
  empty: '当前筛选条件下没有比赛记录',
  loadError: '比赛数据加载失败',
  retry: '重新加载',
  close: '关闭',
  prev: '◀ 上一页',
  next: '下一页 ▶',
  pageInfo: (p: number, tp: number, t: number) => `第 ${p} / ${tp} 页（共 ${t} 场比赛）`,
  regularTime: '🕐 90 分钟常规时间',
  extraTime: '🕑 加时赛',
  penaltyShootout: '⚽ 点球大战',
  sourceDetails: '📖 来源详情',
  notApplicable: '本场比赛无此阶段',
  formalScore: '正式比分：',
  penaltyScoreLabel: '点球比分：',
  noSource: '暂无来源信息',
}

// ============================================================
// 分页 & 数据
// ============================================================
const matches = ref<MatchItem[]>([])
const page = ref(1)
const total = ref(0)
const pageSize = ref(20)
const loading = ref(false)
const error = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function fetchPage(p: number) {
  loading.value = true
  error.value = false
  const res = await fetchMatches(props.filters, p, pageSize.value)
  if (res) {
    matches.value = res.matches
    total.value = res.total
    page.value = res.page
  } else {
    error.value = true
  }
  loading.value = false
}

function goPrev() {
  if (page.value > 1) fetchPage(page.value - 1)
}
function goNext() {
  if (page.value < totalPages.value) fetchPage(page.value + 1)
}

// 筛选变化 → 重置第 1 页
watch(
  () => props.filters,
  () => {
    page.value = 1
    fetchPage(1)
  },
  { deep: true },
)

onMounted(() => fetchPage(1))

// ============================================================
// 比赛详情展开
// ============================================================
const expandedMatchId = ref<string | null>(null)

function toggleDetail(id: string) {
  expandedMatchId.value = expandedMatchId.value === id ? null : id
}
function closeDetail() {
  expandedMatchId.value = null
}

// ============================================================
// 映射：API MatchItem → 视图 TMatch（保留 95c2e42 映射）
// ============================================================
interface TSource {
  source_id: string
  title: string
  url: string | null
}
interface TMatch {
  match_id: string
  match_date: string | null
  tournament_year: number
  stage: string
  stage_name: string
  home_team_name: string
  away_team_name: string
  score: {
    regular_time: { home: number; away: number }
    after_extra_time: { home: number; away: number } | null
    penalties: { home: number; away: number } | null
    display: string
    penalty_display: string | null
  }
  sources: TSource[]
}
interface TStage {
  stage: string
  stage_name: string
  matches: TMatch[]
}

function toMatchScore(m: MatchItem): TMatch['score'] {
  return {
    regular_time: { home: m.home_score_90, away: m.away_score_90 },
    after_extra_time:
      m.home_score_et !== null && m.away_score_et !== null
        ? { home: m.home_score_et, away: m.away_score_et }
        : null,
    penalties:
      m.home_penalties !== null && m.away_penalties !== null
        ? { home: m.home_penalties, away: m.away_penalties }
        : null,
    display: m.score_display,
    penalty_display: m.penalty_score,
  }
}

function toTMatch(m: MatchItem): TMatch {
  return {
    match_id: m.match_id,
    match_date: m.match_date,
    tournament_year: m.tournament_year,
    stage: m.stage,
    stage_name: m.stage_name,
    home_team_name: m.home_team_name,
    away_team_name: m.away_team_name,
    score: toMatchScore(m),
    sources: (m.sources as MatchSourceItem[]).map(s => ({
      source_id: s.source_id,
      title: s.title,
      url: s.url,
    })),
  }
}

const STAGE_ORDER: Record<string, number> = {
  group: 0,
  second_group: 1,
  round_of_16: 2,
  quarter_final: 3,
  semi_final: 4,
  third_place: 5,
  final: 6,
  final_round: 7,
}

const stageGroups = computed<TStage[]>(() => {
  const groups = new Map<string, TMatch[]>()
  for (const m of matches.value) {
    const tm = toTMatch(m)
    const key = m.stage
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(tm)
  }
  return Array.from(groups.entries())
    .sort((a, b) => (STAGE_ORDER[a[0]] ?? 99) - (STAGE_ORDER[b[0]] ?? 99))
    .map(([stage, matches]) => ({
      stage,
      stage_name: matches[0].stage_name,
      matches,
    }))
})

function findTMatch(id: string): TMatch | null {
  for (const s of stageGroups.value) {
    const f = s.matches.find(m => m.match_id === id)
    if (f) return f
  }
  return null
}

const expandedMatchDetail = computed<TMatch | null>(() =>
  expandedMatchId.value ? findTMatch(expandedMatchId.value) : null,
)
</script>

<style scoped>
/* ============================================================
   容器
   ============================================================ */
.timeline-section {
  flex-shrink: 0;
  max-height: 48vh;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  overflow-y: auto;
}

.tl-header-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #1a1a1a;
  border-left: 3px solid #4a90d9;
  padding-left: 10px;
}

.tl-total-badge {
  font-size: 12px;
  color: #888;
  background: #f0f0f0;
  padding: 3px 10px;
  border-radius: 10px;
}

/* ============================================================
   状态占位
   ============================================================ */
.tl-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  color: #999;
  font-size: 14px;
  gap: 8px;
}

.tl-error { color: #c0504d; }
.tl-error-icon { font-size: 32px; }
.tl-empty-icon { font-size: 32px; opacity: 0.5; }

.tl-retry-btn {
  padding: 6px 18px;
  border: 1px solid #c0504d;
  border-radius: 6px;
  background: #fff;
  color: #c0504d;
  cursor: pointer;
  font-size: 13px;
}
.tl-retry-btn:hover { background: #fef2f2; }

/* 骨架屏 */
.tl-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  width: 100%;
}

.tl-skeleton-card {
  height: 88px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
  border-radius: 8px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ============================================================
   阶段分组 + CSS Grid
   ============================================================ */
.tl-stage-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin: 16px 0;
}

.tl-stage-section {
  /* nothing extra needed */
}

.tl-stage-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8ecf0;
}

.tl-stage-dot {
  width: 10px;
  height: 10px;
  background: #4a90d9;
  border-radius: 50%;
  flex-shrink: 0;
}

.tl-stage-name {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #333;
}

.tl-stage-count {
  font-size: 11px;
  color: #999;
  background: #f5f5f5;
  padding: 2px 8px;
  border-radius: 8px;
}

/* CSS Grid 卡片布局 */
.tl-match-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.tl-match-card {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.12s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tl-match-card:hover {
  border-color: #4a90d9;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(74, 144, 217, 0.12);
}

.tl-card-active {
  border-color: #4a90d9;
  box-shadow: 0 0 0 2px rgba(74, 144, 217, 0.18);
}

.tl-card-teams {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.tl-card-home { color: #1a1a1a; }
.tl-card-away { color: #1a1a1a; }
.tl-card-vs {
  font-size: 11px;
  font-weight: 400;
  color: #bbb;
  margin: 0 2px;
}

.tl-card-score {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tl-card-score-main {
  font-size: 18px;
  font-weight: 800;
  color: #1a1a1a;
}

.tl-card-pk {
  font-size: 12px;
  color: #b85c10;
  font-weight: 500;
}

.tl-card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #999;
}

.tl-card-year {
  background: #fef3e5;
  color: #b85c10;
  padding: 1px 8px;
  border-radius: 4px;
  font-weight: 600;
}

/* ============================================================
   翻页控件
   ============================================================ */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding: 6px 0;
}

.pagination-bar button {
  padding: 6px 16px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  background: #fff;
  color: #555;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}
.pagination-bar button:hover:not(:disabled) {
  border-color: #4a90d9;
  color: #4a90d9;
}
.pagination-bar button:disabled {
  color: #ccc;
  cursor: not-allowed;
  border-color: #eee;
}

.page-info {
  font-size: 13px;
  color: #888;
  font-weight: 500;
}

/* ============================================================
   展开详情面板（保持原样式）
   ============================================================ */
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

.tl-vs { font-weight: 400; color: #999; font-size: 13px; }

.tl-tag {
  font-size: 11px;
  font-weight: 600;
  color: #4a90d9;
  background: #e8f0fe;
  padding: 2px 8px;
  border-radius: 4px;
}
.tl-tag-year { background: #fef3e5; color: #b85c10; }

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

.tl-team-name { font-size: 14px; font-weight: 600; color: #555; }
.tl-big-score { font-size: 28px; font-weight: 800; color: #1a1a1a; }
.tl-colon { font-size: 22px; font-weight: 300; color: #bbb; }

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

.tl-src-card { min-width: 240px; }

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

/* ---- 滚动条 ---- */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d0d5dd; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #a0a7b0; }
</style>
