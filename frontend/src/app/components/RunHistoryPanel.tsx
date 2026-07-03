'use client'

// Phase 2 run-history panel: a real, revisitable list of past runs for the
// workspace (GET /workspaces/{id}/runs). Clicking a run loads its full detail
// (GET /runs/{id}) and hands it up so the thread can re-render the past
// answer + dashboard + code + enrichments.

import { useCallback, useEffect, useState } from 'react'
import { getRun, listRuns, type RunDetail, type RunListItem } from '@/lib/api'

interface RunHistoryPanelProps {
  workspaceId: string
  refreshKey: number
  onOpenRun: (run: RunDetail) => void
}

export function RunHistoryPanel({ workspaceId, refreshKey, onOpenRun }: RunHistoryPanelProps) {
  const [runs, setRuns] = useState<RunListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openingId, setOpeningId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRuns(await listRuns(workspaceId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load run history.')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  async function open(run: RunListItem) {
    setOpeningId(run.id)
    try {
      const detail = await getRun(run.id)
      onOpenRun(detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open run.')
    } finally {
      setOpeningId(null)
    }
  }

  return (
    <section
      data-testid="run-history-panel"
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Run history</h2>
        <button
          type="button"
          onClick={() => void load()}
          className="text-[11px] font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          Refresh
        </button>
      </div>

      {loading && (
        <div data-testid="run-history-loading" className="space-y-1.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-9 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
          ))}
        </div>
      )}

      {!loading && error && (
        <p
          data-testid="run-history-error"
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
        >
          {error}
        </p>
      )}

      {!loading && !error && runs.length === 0 && (
        <p data-testid="run-history-empty" className="py-4 text-center text-xs text-slate-400 dark:text-slate-500">
          No questions asked yet. Your run history will appear here.
        </p>
      )}

      {!loading && !error && runs.length > 0 && (
        <ul className="space-y-1">
          {runs.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                data-testid="run-history-item"
                data-run-id={run.id}
                disabled={openingId === run.id}
                onClick={() => void open(run)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition hover:bg-slate-50 disabled:opacity-60 dark:hover:bg-slate-800"
              >
                {run.has_chart && (
                  <span
                    data-testid="run-has-chart"
                    title="This run produced a chart"
                    className="shrink-0 text-blue-500 dark:text-blue-400"
                    aria-hidden
                  >
                    📊
                  </span>
                )}
                <span className="flex-1 truncate text-xs text-slate-700 dark:text-slate-200" title={run.question}>
                  {run.question}
                </span>
                <span
                  className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase ${
                    run.status === 'failed'
                      ? 'bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300'
                      : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
                  }`}
                >
                  {run.status}
                </span>
                <span className="shrink-0 text-[10px] text-slate-400 dark:text-slate-500">
                  {formatWhen(run.created_at)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function formatWhen(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
