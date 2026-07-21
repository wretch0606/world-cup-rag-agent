<template>
  <aside class="sidebar">
    <h3 class="sidebar-title">{{ labels.title }}</h3>

    <!-- 届次 -->
    <div class="filter-block">
      <div class="filter-block-header" @click="toggleGroup('tournament')">
        <span>{{ labels.tournament }}</span>
        <span class="filter-arrow">{{ filterGroupOpen.tournament ? '▾' : '▸' }}</span>
      </div>
      <div v-show="filterGroupOpen.tournament" class="filter-checks filter-checks-scroll-sm">
        <label v-for="y in filterOptions.tournaments" :key="y.year" class="filter-check">
          <input type="checkbox" :value="y.year" v-model="filters.years" />
          <span>{{ y.label }}</span>
        </label>
        <div class="filter-actions">
          <button @click="selectAll('years', filterOptions.tournaments.map(y => y.year))">{{ labels.selectAll }}</button>
          <button @click="clearAll('years')">{{ labels.clearAll }}</button>
        </div>
      </div>
    </div>

    <!-- 球队 -->
    <div class="filter-block">
      <div class="filter-block-header" @click="toggleGroup('team')">
        <span>{{ labels.team }} <span class="filter-count">({{ filterOptions.teams.length }})</span></span>
        <span class="filter-arrow">{{ filterGroupOpen.team ? '▾' : '▸' }}</span>
      </div>
      <div v-show="filterGroupOpen.team" class="filter-checks">
        <!-- 本地搜索框 -->
        <div class="team-search-wrap">
          <span class="team-search-icon">🔍</span>
          <input
            v-model="teamSearchText"
            type="text"
            class="team-search-input"
            :placeholder="labels.searchTeam"
          />
        </div>
        <div class="filter-checks-scroll-lg">
          <label v-for="t in filteredTeams" :key="t.team_id" class="filter-check">
            <input type="checkbox" :value="t.team_id" v-model="filters.teamIds" />
            <span>{{ t.name }}</span>
          </label>
          <div v-if="!filteredTeams.length" class="filter-empty-hint">{{ labels.noTeamMatch }}</div>
        </div>
        <div class="filter-actions">
          <button @click="selectAll('teamIds', filterOptions.teams.map(t => t.team_id))">{{ labels.selectAll }}</button>
          <button @click="clearAll('teamIds')">{{ labels.clearAll }}</button>
        </div>
      </div>
    </div>

    <!-- 阶段 -->
    <div class="filter-block">
      <div class="filter-block-header" @click="toggleGroup('stage')">
        <span>{{ labels.stage }}</span>
        <span class="filter-arrow">{{ filterGroupOpen.stage ? '▾' : '▸' }}</span>
      </div>
      <div v-show="filterGroupOpen.stage" class="filter-checks">
        <label v-for="s in filterOptions.stages" :key="s.value" class="filter-check">
          <input type="checkbox" :value="s.value" v-model="filters.stages" />
          <span>{{ s.label }}</span>
        </label>
        <div class="filter-actions">
          <button @click="selectAll('stages', filterOptions.stages.map(s => s.value))">{{ labels.selectAll }}</button>
          <button @click="clearAll('stages')">{{ labels.clearAll }}</button>
        </div>
      </div>
    </div>

    <!-- 比赛结果 -->
    <div class="filter-block">
      <div class="filter-block-header" @click="toggleGroup('resultType')">
        <span>{{ labels.resultType }}</span>
        <span class="filter-arrow">{{ filterGroupOpen.resultType ? '▾' : '▸' }}</span>
      </div>
      <div v-show="filterGroupOpen.resultType" class="filter-checks">
        <label v-for="r in filterOptions.result_types" :key="r.value" class="filter-check">
          <input type="checkbox" :value="r.value" v-model="filters.resultTypes" />
          <span>{{ r.label }}</span>
        </label>
      </div>
    </div>

    <!-- 点球 -->
    <div class="filter-block">
      <div class="filter-block-header">
        <span>{{ labels.penaltyOnly }}</span>
      </div>
      <label class="filter-check" style="padding-left:4px">
        <input type="checkbox" v-model="filters.hasPenalties" />
        <span>{{ labels.penaltyHint }}</span>
      </label>
    </div>

    <button class="sidebar-reset" @click="$emit('reset')">{{ labels.reset }}</button>
  </aside>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import type { FilterOptionsData, FiltersState } from '@/api'

// ============================================================
// Props & Emits
// ============================================================
const props = defineProps<{
  filterOptions: FilterOptionsData
  loading?: boolean
}>()

defineEmits<{
  reset: []
}>()

const filters = defineModel<FiltersState>('filters', { required: true })

// ============================================================
// 文案
// ============================================================
const labels = {
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
  searchTeam: '搜索球队...',
  noTeamMatch: '无匹配球队',
}

// ============================================================
// 折叠 / 展开
// ============================================================
const filterGroupOpen = reactive({
  tournament: true,
  team: false,
  stage: true,
  resultType: false,
})

function toggleGroup(k: keyof typeof filterGroupOpen) {
  filterGroupOpen[k] = !filterGroupOpen[k]
}

// ============================================================
// 球队搜索
// ============================================================
const teamSearchText = ref('')

const filteredTeams = computed(() => {
  const q = teamSearchText.value.trim().toLowerCase()
  if (!q) return props.filterOptions.teams
  return props.filterOptions.teams.filter((t: { name: string }) => t.name.toLowerCase().includes(q))
})

// ============================================================
// 全选 / 清空
// ============================================================
function selectAll(field: keyof FiltersState, values: any[]) {
  (filters.value as any)[field] = [...values]
}

function clearAll(field: keyof FiltersState) {
  if (field === 'hasPenalties') {
    filters.value.hasPenalties = false
  } else {
    (filters.value as any)[field] = []
  }
}
</script>

<style scoped>
/* ---- 侧栏 ---- */
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

.filter-count { font-weight: 400; color: #999; }

.filter-arrow { font-size: 11px; color: #999; }

.filter-checks {
  display: flex;
  flex-direction: column;
  padding: 2px 4px;
}

/* 届次：最多 200px */
.filter-checks-scroll-sm {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 2px 4px;
}

/* 球队：更多高度 + 搜索框 */
.filter-checks-scroll-lg {
  max-height: 240px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* 球队搜索 */
.team-search-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 6px 6px 8px;
  margin-bottom: 2px;
  background: #f7f9fc;
  border: 1px solid #e0e5ec;
  border-radius: 6px;
  position: sticky;
  top: 0;
  z-index: 1;
}

.team-search-icon {
  font-size: 12px;
  flex-shrink: 0;
  opacity: 0.6;
}

.team-search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  outline: none;
  color: #333;
  padding: 2px 0;
}
.team-search-input::placeholder { color: #aaa; }

.filter-empty-hint {
  padding: 10px 6px;
  font-size: 12px;
  color: #aaa;
  text-align: center;
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

/* 重置按钮 — sticky 固定在侧栏底部 */
.sidebar-reset {
  margin-top: auto;
  padding: 10px 0;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  background: #fff;
  color: #555;
  font-size: 14px;
  cursor: pointer;
  position: sticky;
  bottom: 0;
  z-index: 10;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.04);
}
.sidebar-reset:hover { background: #f0f0f0; }

/* ---- 滚动条 ---- */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d0d5dd; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #a0a7b0; }
</style>
