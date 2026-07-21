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
//   · 数组展开为重复键：years=2018&years=2022
// ============================================================
function buildParams(params: Record<string, unknown>): string {
  const sp = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      value.forEach(v => sp.append(key, String(v)))
    } else if (typeof value === 'boolean') {
      sp.append(key, value ? 'true' : 'false')
    } else {
      sp.append(key, String(value))
    }
  }
  return sp.toString()
}

// ============================================================
// 公共响应外壳（契约 §3）
// ============================================================
export interface ApiResponse<T> {
  success: boolean
  code: string
  message: string
  data: T
  trace_id: string
  timestamp: string
}

export interface ApiErrorDetail {
  field?: string
  reason?: string
  error?: string
}

export interface ApiErrorResponse {
  success: false
  code: string
  message: string
  data: null
  trace_id: string
  timestamp: string
  retryable: boolean
  details: ApiErrorDetail[]
}

// ============================================================
// 响应拦截器 — 保留 AxiosResponse，由各函数提取 response.data.data
// ============================================================
api.interceptors.response.use(
  (res) => res,
  (err) => {
    console.warn('[API] 请求失败:', err.config?.url, err.message)
    return Promise.reject(err)
  },
)

// ============================================================
// 内部 helper — 提取业务 data
// ============================================================
function extractData<T>(res: { data: ApiResponse<T> }): T {
  return res.data.data
}

// ============================================================
// 通用筛选参数（snake_case，契约 §3）
// ============================================================
export interface QueryFilters {
  years?: number[]
  team_ids?: string[]
  stages?: string[]
  result_types?: string[]
  has_penalties?: boolean | null
  match_ids?: string[]
}

/** 前端组件内部使用的筛选状态（空数组表示不筛选）。 */
export interface FiltersState {
  years: number[]
  teamIds: string[]
  stages: string[]
  resultTypes: string[]
  hasPenalties: boolean
}

// ============================================================
// GET /api/filter-options
// ============================================================
export interface TournamentOption {
  year: number
  label: string
  host: string | null
}

export interface TeamOption {
  team_id: string
  name: string
}

export interface StageOption {
  value: string
  label: string
  order: number
}

export interface ResultTypeOption {
  value: string
  label: string
}

export interface FilterOptionsData {
  data_status: string
  tournaments: TournamentOption[]
  teams: TeamOption[]
  stages: StageOption[]
  result_types: ResultTypeOption[]
}

export async function fetchFilterOptions(): Promise<FilterOptionsData> {
  const res = await api.get<ApiResponse<FilterOptionsData>>('/filter-options')
  return extractData(res)
}

// ============================================================
// GET /api/matches
// ============================================================
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

export interface MatchItem {
  match_id: string
  tournament_year: number
  match_date: string
  stage: string
  stage_name: string
  home_team: TeamRef
  away_team: TeamRef
  score: MatchScore
  result_type: string
  winner_team: TeamRef | null
}

export interface MatchesData {
  data_status: string
  items: MatchItem[]
  total: number
  page: number
  page_size: number
  applied_filters: Record<string, unknown>
}

export async function fetchMatches(
  filters?: QueryFilters,
  page?: number,
  pageSize?: number,
): Promise<MatchesData> {
  const params: Record<string, unknown> = {}
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && (!Array.isArray(v) || v.length > 0)) {
        params[k] = v
      }
    }
  }
  if (page !== undefined) params.page = page
  if (pageSize !== undefined) params.page_size = pageSize
  const res = await api.get<ApiResponse<MatchesData>>('/matches', {
    params,
    paramsSerializer: { serialize: buildParams },
  })
  return extractData(res)
}

// ============================================================
// GET /api/graph
// ============================================================
export interface GraphNode {
  id: string
  name: string
  type: string
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  match_id: string
  tournament_year: number
  stage: string
  stage_name: string
  result_type: string
  winner_team_id: string | null
  label: string
}

export interface GraphStats {
  node_count: number
  edge_count: number
  truncated: boolean
}

export interface GraphData {
  data_status: string
  scope: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
  applied_filters: Record<string, unknown>
}

export async function fetchGraph(filters?: QueryFilters): Promise<GraphData> {
  const params: Record<string, unknown> = {}
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && (!Array.isArray(v) || v.length > 0)) {
        params[k] = v
      }
    }
  }
  const res = await api.get<ApiResponse<GraphData>>('/graph', {
    params,
    paramsSerializer: { serialize: buildParams },
  })
  return extractData(res)
}

// ============================================================
// POST /api/agent/query
// ============================================================
export interface QueryFiltersSnake {
  years: number[]
  team_ids: string[]
  stages: string[]
  result_types: string[]
  match_ids: string[]
  has_penalties: boolean | null
}

export interface QueryRequest {
  question: string
  session_id: string | null
  filters: QueryFiltersSnake
  debug: boolean
}

export interface ApiFact {
  fact_type: string
  fact_id: string
  match_id: string | null
  tournament_year?: number
  stage?: string
  stage_name?: string
  home_team?: TeamRef
  away_team?: TeamRef
  score?: MatchScore
  result_type?: string
  winner_team?: TeamRef | null
  text: string
  source_ids: string[]
}

export interface ApiSourceItem {
  source_id: string
  title: string
  url: string | null
  page: number | null
  document_id: string | null
  data_version: string | null
  used_for_fact_ids: string[]
}

export interface QueryWarning {
  code: string
  message: string
  component: string
  retryable?: boolean
}

export interface QueryTiming {
  routing_ms: number
  sql_ms: number
  retrieval_ms: number
  generation_ms: number
  total_ms: number
}

export interface QueryResponseData {
  data_status: string
  status: string
  intent: string
  route: string
  answer: string
  needs_clarification: boolean
  clarification_question: string | null
  facts: ApiFact[]
  sources: ApiSourceItem[]
  graph: GraphData & { scope: string }
  applied_filters: Record<string, unknown>
  confidence: number | null
  warnings: QueryWarning[]
  timing: QueryTiming
}

export async function postQuery(
  question: string,
  filters?: QueryFilters,
): Promise<QueryResponseData> {
  const body: QueryRequest = {
    question,
    session_id: null,
    filters: {
      years: filters?.years ?? [],
      team_ids: filters?.team_ids ?? [],
      stages: filters?.stages ?? [],
      result_types: filters?.result_types ?? [],
      match_ids: filters?.match_ids ?? [],
      has_penalties: filters?.has_penalties ?? null,
    },
    debug: false,
  }
  const res = await api.post<ApiResponse<QueryResponseData>>('/agent/query', body)
  return extractData(res)
}

// ============================================================
// GET /api/matches/{match_id}
// ============================================================
export interface MatchDetailData extends MatchItem {
  data_status: string
  venue: string | null
  city: string | null
  timeline: {
    regular_time: unknown[]
    extra_time: unknown[]
    shootout: {
      available: boolean
      home_score: number
      away_score: number
      events: unknown[]
      message: string
    }
  }
  sources: ApiSourceItem[]
}

export async function fetchMatchDetail(matchId: string): Promise<MatchDetailData> {
  const res = await api.get<ApiResponse<MatchDetailData>>(`/matches/${matchId}`)
  return extractData(res)
}

// ============================================================
// GET /api/teams/{team_id}/relations
// ============================================================
export interface TeamRelationsData {
  data_status: string
  team: TeamRef | null
  stats: {
    matches: number
    regulation_or_extra_time_wins: number
    draws: number
    penalty_advances: number
    losses: number
  }
  matches: MatchItem[]
  graph: GraphData & { scope: string }
  total: number
  page: number
  page_size: number
  applied_filters: Record<string, unknown>
}

export async function fetchTeamRelations(teamId: string): Promise<TeamRelationsData> {
  const res = await api.get<ApiResponse<TeamRelationsData>>(`/teams/${teamId}/relations`)
  return extractData(res)
}

// ============================================================
// GET /api/documents
// ============================================================
export interface DocumentItem {
  document_id: string
  title: string
  source_id: string
  file_type: string
  parse_status: string
  chunk_count: number
  parsed_at: string | null
  data_version: string
}

export interface DocumentsData {
  data_status: string
  items: DocumentItem[]
  total: number
  page: number
  page_size: number
  applied_filters: Record<string, unknown>
}

export async function fetchDocuments(): Promise<DocumentsData> {
  const res = await api.get<ApiResponse<DocumentsData>>('/documents')
  return extractData(res)
}
