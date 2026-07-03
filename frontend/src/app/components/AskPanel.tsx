'use client'

import { useState } from 'react'
import type { AskResult } from '@/lib/api'
import { formatCell } from '@/lib/formatNumber'
import { Stub, StubButton } from './Stub'

interface AskPanelProps {
  canAsk: boolean
  loading: boolean
  error: string | null
  result: AskResult | null
  onAsk: (question: string) => void
}

export function AskPanel({ canAsk, loading, error, result, onAsk }: AskPanelProps) {
  const [question, setQuestion] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || !canAsk || loading) return
    onAsk(q)
  }

  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold text-gray-900">Ask a question</h2>

      <form onSubmit={submit} className="space-y-3">
        <div className="flex items-center gap-2 text-[11px] text-gray-400">
          <StubButton label="Streaming" phase="Phase 2" />
        </div>
        <div className="flex gap-2">
          <input
            data-testid="ask-input"
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={!canAsk || loading}
            placeholder={
              canAsk
                ? 'e.g. What is the total outstanding principal?'
                : 'Upload a CSV to start asking questions.'
            }
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
          />
          <button
            type="submit"
            data-testid="ask-submit"
            disabled={!canAsk || loading || !question.trim()}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Running…' : 'Ask'}
          </button>
        </div>
      </form>

      {loading && (
        <div
          data-testid="ask-loading"
          className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-4 text-sm text-gray-500 shadow-sm"
        >
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
          The agent is writing and running pandas locally…
        </div>
      )}

      {error && !loading && (
        <div
          data-testid="ask-error"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {result && !loading && <AnswerCard result={result} />}
    </section>
  )
}

function AnswerCard({ result }: { result: AskResult }) {
  const [showCode, setShowCode] = useState(false)
  const failed = result.status === 'failed'

  return (
    <div
      data-testid="answer-card"
      className={`space-y-5 rounded-xl border bg-white p-6 shadow-sm ${
        failed ? 'border-red-200' : 'border-gray-200'
      }`}
    >
      {/* Answer */}
      <div>
        <div className="mb-1 flex items-center gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400">Answer</h3>
          {result.attempts > 1 && (
            <span
              data-testid="retry-badge"
              className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700"
              title="The first code attempt errored; the agent fixed it and retried."
            >
              fixed and retried · {result.attempts} attempts
            </span>
          )}
          {failed && (
            <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-700">
              run failed
            </span>
          )}
        </div>
        <p
          data-testid="answer-text"
          className={`whitespace-pre-wrap text-sm leading-relaxed ${
            failed ? 'text-red-700' : 'text-gray-900'
          }`}
        >
          {result.answer}
        </p>
      </div>

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
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
            aria-expanded={showCode}
          >
            <span className={`transition-transform ${showCode ? 'rotate-90' : ''}`}>▸</span>
            {showCode ? 'Hide code' : 'Show code'}
          </button>
          {showCode && (
            <pre
              data-testid="code-panel"
              className="mt-2 overflow-x-auto rounded-lg border border-gray-200 bg-gray-900 p-4 text-xs leading-relaxed text-gray-100"
            >
              <code>{result.generated_code}</code>
            </pre>
          )}
        </div>
      )}

      {/* Phase 2 enrichment stubs */}
      <div className="grid gap-2 sm:grid-cols-2">
        <Stub title="Chart" phase="Phase 2" compact>
          An interactive chart will render here when the question suits one.
        </Stub>
        <Stub title="Estimated cost" phase="Phase 2" compact>
          Per-query token cost will show here.
        </Stub>
        <Stub title="Suggested follow-ups" phase="Phase 2" compact>
          2–3 follow-up questions will appear as chips.
        </Stub>
        <Stub title="Data-quality flags" phase="Phase 2" compact>
          Nulls / duplicates / outliers detected in this answer.
        </Stub>
      </div>

      {/* Phase 3 action stubs */}
      <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-3">
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
    <div className="overflow-x-auto rounded-lg border border-gray-100">
      <table className="w-full text-left text-xs" data-testid="result-table">
        <thead className="bg-gray-50 text-gray-500">
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
            <tr key={i} className="border-t border-gray-100">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 font-mono text-gray-700">
                  {formatCell(cell, table.columns[j])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.rows.length > MAX_ROWS && (
        <p className="px-3 py-1.5 text-[11px] text-gray-400">
          Showing first {MAX_ROWS} of {table.rows.length.toLocaleString()} rows.
        </p>
      )}
    </div>
  )
}
