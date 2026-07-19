import axios from 'axios'

// ============================================================
// Axios 实例
// ============================================================
const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ============================================================
// 请求参数序列化
//   · 驼峰 → 下划线：teamIds → team_ids
//   · 数组展开为重复键：years=2018&years=2022（禁用逗号拼接）
// ============================================================
function buildParams(params: Record<string, unknown>): string {
  const sp = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    const snakeKey = key.replace(/[A-Z]/g, (m) => '_' + m.toLowerCase())
    if (Array.isArray(value)) {
      value.forEach(v => sp.append(snakeKey, String(v)))
    } else if (typeof value === 'boolean') {
      sp.append(snakeKey, value ? '1' : '0')
    } else {
      sp.append(snakeKey, String(value))
    }
  }
  return sp.toString()
}

// ============================================================
// 响应拦截器
// ============================================================
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.warn('[API] 请求失败:', err.config?.url, err.message)
    return Promise.resolve(null)
  },
)

// ============================================================
// 类型定义（对齐 rag-contract-v1.0）
// ============================================================

// ---- 通用筛选参数（前端驼峰命名） ----
export interface QueryFilters {
  years?: number[]
  teamIds?: string[]
  stages?: string[]
  resultTypes?: string[]
  hasPenalties?: boolean
}

// ---- GET /api/filter-options ----
export interface FilterOptionTeam {
  id: string
  name: string
}
export interface FilterOptionStage {
  value: string
  label: string
}
export interface FilterOptionResultType {
  value: string
  label: string
}

export interface FilterOptionsResponse {
  tournaments: number[]
  teams: FilterOptionTeam[]
  stages: FilterOptionStage[]
  resultTypes: FilterOptionResultType[]
}

// ---- GET /api/matches ----
export interface MatchSourceItem {
  source_id: string
  title: string
  url: string | null
}

export interface MatchItem {
  match_id: string
  match_date: string | null
  tournament_year: number
  stage: string
  stage_name: string
  home_team_id: string
  home_team_name: string
  away_team_id: string
  away_team_name: string
  home_score_90: number
  away_score_90: number
  home_score_et: number | null
  away_score_et: number | null
  home_penalties: number | null
  away_penalties: number | null
  score_display: string
  penalty_score: string | null
  result_type: string
  winner_team_id: string | null
  sources: MatchSourceItem[]
}

export interface MatchesResponse {
  matches: MatchItem[]
}

// ---- GET /api/graph ----
export interface GraphNode {
  id: string
  name: string
  type: string
}
export interface GraphEdge {
  id: string
  source: string
  target: string
  match_id: string
  label: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ---- POST /api/query —— B 统一响应（契约 §10） ----
export interface TeamRef {
  team_id: string
  name: string
}

export interface ScoreDetail {
  home: number
  away: number
}

export interface MatchScore {
  regular_time: ScoreDetail
  after_extra_time: ScoreDetail | null
  penalties: ScoreDetail | null
  display: string
  penalty_display: string | null
}

export interface ApiFact {
  fact_id: string
  match_id: string
  stage_name: string
  home_team: TeamRef
  away_team: TeamRef
  score: MatchScore
  winner_team: TeamRef | null
}

export interface ApiSourceItem {
  source_id: string
  title: string
  url: string | null
}

export interface QueryWarning {
  code: string
  message: string
  component: string
  retryable: boolean
}

/** B 组装的前端统一响应（契约 §10） */
export interface QueryResponse {
  intent: string
  answer: string
  facts: ApiFact[]
  sources: ApiSourceItem[]
  graph: {
    nodes: GraphNode[]
    edges: GraphEdge[]
  }
  trace_id: string
  status: string
  warnings: QueryWarning[]
  /** MVP 阶段固定 null，非 null 时才展示置信度 UI */
  confidence?: number | null
}

// ============================================================
// API 函数
// ============================================================

/** 获取筛选器可用选项 */
export async function fetchFilterOptions(): Promise<FilterOptionsResponse | null> {
  return api.get('/filter-options') as unknown as Promise<FilterOptionsResponse | null>
}

/** 获取比赛列表（支持多选筛选） */
export async function fetchMatches(filters?: QueryFilters): Promise<MatchesResponse | null> {
  const params = filters
    ? Object.fromEntries(
        Object.entries(filters).filter(([, v]) =>
          v !== undefined && v !== null && (Array.isArray(v) ? v.length > 0 : true),
        ),
      )
    : {}
  return api.get('/matches', {
    params,
    paramsSerializer: { serialize: buildParams },
  }) as unknown as Promise<MatchesResponse | null>
}

/** 获取知识图谱数据（支持筛选） */
export async function fetchGraph(filters?: QueryFilters): Promise<GraphResponse | null> {
  const params = filters
    ? Object.fromEntries(
        Object.entries(filters).filter(([, v]) =>
          v !== undefined && v !== null && (Array.isArray(v) ? v.length > 0 : true),
        ),
      )
    : {}
  return api.get('/graph', {
    params,
    paramsSerializer: { serialize: buildParams },
  }) as unknown as Promise<GraphResponse | null>
}

/** 提交问答 → B 统一响应 */
export async function postQuery(
  question: string,
  filters?: QueryFilters,
): Promise<QueryResponse | null> {
  const body: Record<string, unknown> = { question }
  if (filters) {
    body.filters = filters
  }
  return api.post('/query', body) as unknown as Promise<QueryResponse | null>
}
