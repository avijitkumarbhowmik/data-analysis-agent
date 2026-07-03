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

// ---- Phase 2 enrichment shapes (mirror spec/api.md + capability specs) ----

export interface ChartSeries {
  key: string
  label: string
}

export interface Kpi {
  label: string
  value: number
  format: 'percent' | 'number'
  seriesKey: string | null
  emphasis: boolean
}

export interface CategoryBar {
  label: string
  total: number
  segments: Record<string, number>
}

export interface ChartPanel {
  heading: string
  axisLabel: string
  categories: CategoryBar[]
}

export interface LinePoint {
  x: string | number
  y: number
  series?: string
}

export interface ChartSpec {
  kind: 'dashboard' | 'line' | 'bar'
  title: string
  subtitle: string
  series: ChartSeries[]
  kpis?: Kpi[]
  charts?: ChartPanel[]
  points?: LinePoint[]
}

export interface CostInfo {
  input_tokens: number
  output_tokens: number
  usd: number
}

export interface DataQualityFlag {
  level: 'info' | 'warn'
  column: string | null
  message: string
}

export interface AskResult {
  run_id: string
  answer: string
  generated_code: string
  result_table: ResultTable | null
  status: string
  attempts: number
  // Phase 2 enrichments — always present on a successful run (may be null/[]).
  chart_spec?: ChartSpec | null
  data_quality_flags?: DataQualityFlag[]
  followups?: string[]
  cost?: CostInfo | null
  clarifying_question?: string
}

export interface RunListItem {
  id: string
  question: string
  status: string
  created_at: string
  has_chart: boolean
}

export interface RunDetail extends AskResult {
  question: string
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

// ---- Run history (Phase 2) ----

export function listRuns(workspaceId: string): Promise<RunListItem[]> {
  return request<RunListItem[]>(`/workspaces/${workspaceId}/runs`)
}

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}`)
}

// ---- Streaming ask (Phase 2, SSE) ----
//
// POSTs to /ask/stream and consumes a `text/event-stream`. Because this is a
// POST (EventSource only supports GET) we read the raw body stream and parse
// SSE frames by hand. The SSE endpoint streams RAW events (not the {data,error}
// envelope): `event: delta`/`data:{text}`, one terminal `event: final`/`data:`
// = the full /ask payload, and `event: error`/`data:{message}` on failure.
//
// askStream RESOLVES only after a `final` frame is delivered to onFinal. It
// THROWS on any failure (network, non-2xx, `error` event, or a stream that ends
// without a `final`), so callers can transparently fall back to non-streaming
// ask(). Deltas already delivered before a throw are the caller's to discard.

export interface AskStreamHandlers {
  onDelta: (text: string) => void
  onFinal: (result: AskResult) => void
  onError?: (message: string) => void
}

interface SseEvent {
  event: string
  data: string
}

function parseSseBlock(raw: string): SseEvent {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).replace(/^ /, ''))
    }
  }
  return { event, data: dataLines.join('\n') }
}

export async function askStream(
  workspaceId: string,
  question: string,
  datasetId: string | null,
  handlers: AskStreamHandlers,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`/workspaces/${workspaceId}/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ question, dataset_id: datasetId }),
    })
  } catch {
    throw new ApiError('Streaming unavailable — is the server running?', 'NETWORK', 0)
  }

  if (!res.ok || !res.body) {
    throw new ApiError(`Streaming request failed (${res.status})`, 'STREAM', res.status)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalReceived = false

  const dispatch = (block: string) => {
    const trimmed = block.trim()
    if (!trimmed) return
    const { event, data } = parseSseBlock(block)
    if (event === 'delta') {
      try {
        const parsed = JSON.parse(data) as { text?: string }
        if (parsed.text) handlers.onDelta(parsed.text)
      } catch {
        /* ignore malformed delta frame */
      }
    } else if (event === 'final') {
      const result = JSON.parse(data) as AskResult
      finalReceived = true
      handlers.onFinal(result)
    } else if (event === 'error') {
      let message = 'Streaming error'
      try {
        message = (JSON.parse(data) as { message?: string }).message ?? message
      } catch {
        /* keep default */
      }
      handlers.onError?.(message)
      throw new ApiError(message, 'STREAM', res.status)
    }
  }

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      dispatch(block)
    }
  }
  if (buffer.trim()) dispatch(buffer)

  if (!finalReceived) {
    throw new ApiError('Stream ended before completion', 'STREAM', res.status)
  }
}
