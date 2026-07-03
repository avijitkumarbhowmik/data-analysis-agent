// API client for the data-analysis agent.
//
// The backend (FastAPI) is served on the same origin (:8001) with the app
// static-exported at /app/. Because the API routers are mounted at the origin
// root (see spec/api.md: `POST /workspaces`, `GET /workspaces/{id}`, ...), we
// call absolute-from-root paths like `/workspaces`. A leading-slash path is
// origin-relative and is NOT affected by Next.js `basePath: '/app'`, so these
// resolve to http://localhost:8001/workspaces as intended.
//
// Envelope convention (boilerplate): success -> { data, error }, error ->
// HTTP status with { detail: { code, message } }.

export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    // Fetch itself rejected -> the server is unreachable / network down.
    throw new ApiError('Network error — is the server running?', 'NETWORK', 0)
  }

  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    body = null
  }

  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } } | null)?.detail
    throw new ApiError(
      detail?.message ?? `Request failed (${res.status})`,
      detail?.code ?? 'ERROR',
      res.status,
    )
  }

  return (body as { data: T }).data
}

// ---- Types (mirror spec/api.md) ----

export interface WorkspaceListItem {
  id: string
  name: string
  dataset_count: number
  updated_at: string
}

export interface ColumnSchema {
  name: string
  dtype: string
  stats?: Record<string, unknown>
}

export interface DatasetSummary {
  id: string
  name: string
  filename: string
  row_count: number
  column_count: number
  schema: ColumnSchema[]
  pii_columns?: string[]
}

export interface RecentRun {
  id: string
  question: string
  status: string
  created_at: string
}

export interface WorkspaceDetail {
  id: string
  name: string
  datasets: DatasetSummary[]
  recent_runs: RecentRun[]
}

export interface CreatedWorkspace {
  id: string
  name: string
  created_at: string
}

export interface ResultTable {
  columns: string[]
  rows: (string | number | boolean | null)[][]
}

export interface AskResult {
  run_id: string
  answer: string
  generated_code: string
  result_table: ResultTable | null
  status: string
  attempts: number
  // Phase 2/3 optional enrichments — ignored in Phase 1.
  chart_spec?: unknown
  data_quality_flags?: unknown[]
  followups?: unknown[]
  cost?: unknown
  clarifying_question?: string
}

// ---- Calls ----

export function listWorkspaces(): Promise<WorkspaceListItem[]> {
  return request<WorkspaceListItem[]>('/workspaces')
}

export function createWorkspace(name: string): Promise<CreatedWorkspace> {
  return request<CreatedWorkspace>('/workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function getWorkspace(id: string): Promise<WorkspaceDetail> {
  return request<WorkspaceDetail>(`/workspaces/${id}`)
}

export function uploadDataset(workspaceId: string, file: File): Promise<DatasetSummary> {
  const form = new FormData()
  form.append('file', file)
  return request<DatasetSummary>(`/workspaces/${workspaceId}/datasets`, {
    method: 'POST',
    body: form,
  })
}

export function ask(
  workspaceId: string,
  question: string,
  datasetId: string | null,
): Promise<AskResult> {
  return request<AskResult>(`/workspaces/${workspaceId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, dataset_id: datasetId }),
  })
}
