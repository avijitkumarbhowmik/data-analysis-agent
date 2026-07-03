'use client'

import { useEffect, useRef, useState } from 'react'
import type { AskResult } from '@/lib/api'
import { formatCell } from '@/lib/formatNumber'
import { StubButton } from './Stub'
import { Dashboard } from './Dashboard'
import { CostBadge, DataQualityBadges, FollowupChips } from './Enrichments'

// A single conversation turn within a workspace (Phase 2 chat thread). While a
// turn streams, `streamingText` fills progressively and `result` is null; on the
// terminal `final` event (or the non-streaming fallback) `result` is populated
// with the full enriched payload.
export interface ConversationTurn {
  id: string
  question: string
  streamingText: string
  result: AskResult | null
  status: 'streaming' | 'done' | 'error'
  error: string | null
}

interface AskPanelProps {
  canAsk: boolean
  loading: boolean
  error: string | null
  turns: ConversationTurn[]
  onAsk: (question: string) => void
}

export function AskPanel({ canAsk, loading, error, turns, onAsk }: AskPanelProps) {
  const [question, setQuestion] = useState('')
  const threadEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [turns])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || !canAsk || loading) return
    onAsk(q)
    setQuestion('')
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Conversation</h2>
        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
          live · streaming
        </span>
      </div>

      {/* Conversation thread */}
      {turns.length > 0 && (
        <div data-testid="conversation-thread" className="space-y-6">
          {turns.map((turn) => (
            <TurnView key={turn.id} turn={turn} onAsk={onAsk} disabled={loading} />
          ))}
          <div ref={threadEndRef} />
        </div>
      )}

      {/* Ask input (bottom, chat-style) */}
      <form onSubmit={submit} className="flex gap-2">
        <input
          data-testid="ask-input"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!canAsk || loading}
          placeholder={
            turns.length > 0
              ? 'Ask a follow-up…'
              : 'e.g. show the payment-mode mix by region'
          }
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
        />
        <button
          type="submit"
          data-testid="ask-submit"
          disabled={!canAsk || loading || !question.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Running…' : 'Ask'}
        </button>
      </form>

      {error && !loading && (
        <div
          data-testid="ask-error"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
        >
          {error}
        </div>
      )}
    </section>
  )
}

function TurnView({
  turn,
  onAsk,
  disabled,
}: {
  turn: ConversationTurn
  onAsk: (q: string) => void
  disabled: boolean
}) {
  return (
    <div className="space-y-3">
      {/* User question */}
      <div className="flex justify-end">
        <div
          data-testid="turn-question"
          className="max-w-[85%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white shadow-sm"
        >
          {turn.question}
        </div>
      </div>

      {/* Assistant answer / streaming / error */}
      {turn.status === 'streaming' && !turn.result && (
        <div
          data-testid="turn-streaming"
          className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
        >
          <span className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
          <div className="min-w-0">
            {turn.streamingText ? (
              <p className="whitespace-pre-wrap leading-relaxed">{turn.streamingText}</p>
            ) : (
              <p className="text-slate-400 dark:text-slate-500">
                The agent is writing and running pandas locally…
              </p>
            )}
          </div>
        </div>
      )}

      {turn.status === 'error' && (
        <div
          data-testid="turn-error"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
        >
          {turn.error ?? 'The question could not be answered.'}
        </div>
      )}

      {turn.result && <AnswerCard result={turn.result} onAsk={onAsk} disabled={disabled} />}
    </div>
  )
}

function AnswerCard({
  result,
  onAsk,
  disabled,
}: {
  result: AskResult
  onAsk: (q: string) => void
  disabled: boolean
}) {
  const [showCode, setShowCode] = useState(false)
  const failed = result.status === 'failed'

  return (
    <div
      data-testid="answer-card"
      className={`space-y-4 rounded-xl border bg-white p-6 shadow-sm dark:bg-slate-900 ${
        failed ? 'border-red-200 dark:border-red-900' : 'border-slate-200 dark:border-slate-700'
      }`}
    >
      {/* Header row: label + retry/fail badges + cost */}
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
          Answer
        </h3>
        {result.attempts > 1 && (
          <span
            data-testid="retry-badge"
            className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
            title="The first code attempt errored; the agent fixed it and retried."
          >
            fixed and retried · {result.attempts} attempts
          </span>
        )}
        {failed && (
          <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-700 dark:bg-red-950/40 dark:text-red-300">
            run failed
          </span>
        )}
        <div className="ml-auto">
          <CostBadge cost={result.cost} />
        </div>
      </div>

      {/* Data-quality flags */}
      <DataQualityBadges flags={result.data_quality_flags} />

      {/* Answer text */}
      <p
        data-testid="answer-text"
        className={`whitespace-pre-wrap text-sm leading-relaxed ${
          failed ? 'text-red-700 dark:text-red-300' : 'text-slate-900 dark:text-slate-100'
        }`}
      >
        {result.answer}
      </p>

      {/* Dashboard / chart (only when the backend emits a chart_spec) */}
      {result.chart_spec && <Dashboard spec={result.chart_spec} />}

      {/* Result table */}
      {result.result_table && result.result_table.columns.length > 0 && (
        <ResultTable table={result.result_table} />
      )}

      {/* Collapsible code */}
      {result.generated_code && (
        <div>
          <button
            type="button"
            data-testid="show-code-toggle"
            onClick={() => setShowCode((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-expanded={showCode}
          >
            <span className={`transition-transform ${showCode ? 'rotate-90' : ''}`}>▸</span>
            {showCode ? 'Hide code' : 'Show code'}
          </button>
          {showCode && (
            <pre
              data-testid="code-panel"
              className="mt-2 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 p-4 text-xs leading-relaxed text-slate-100"
            >
              <code>{result.generated_code}</code>
            </pre>
          )}
        </div>
      )}

      {/* Follow-up chips — click asks the next turn with prior context */}
      <FollowupChips followups={result.followups} onAsk={onAsk} disabled={disabled} />

      {/* Phase 3 action stubs (labelled "coming soon", never a dead button) */}
      <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
        <StubButton label="Save cleaned dataset" phase="Phase 3" />
        <StubButton label="Download CSV" phase="Phase 3" />
        <StubButton label="Download chart" phase="Phase 3" />
      </div>
    </div>
  )
}

function ResultTable({ table }: { table: NonNullable<AskResult['result_table']> }) {
  const MAX_ROWS = 50
  const rows = table.rows.slice(0, MAX_ROWS)
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-100 dark:border-slate-800">
      <table className="w-full text-left text-xs" data-testid="result-table">
        <thead className="bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
          <tr>
            {table.columns.map((c) => (
              <th key={c} className="px-4 py-2.5 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 font-mono text-slate-700 dark:text-slate-300">
                  {formatCell(cell, table.columns[j])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.rows.length > MAX_ROWS && (
        <p className="px-3 py-1.5 text-[11px] text-slate-400 dark:text-slate-500">
          Showing first {MAX_ROWS} of {table.rows.length.toLocaleString()} rows.
        </p>
      )}
    </div>
  )
}
