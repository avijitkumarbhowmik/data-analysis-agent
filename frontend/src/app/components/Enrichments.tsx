'use client'

// Small Phase 2 enrichment surfaces rendered alongside an answer:
//   - CostBadge          — per-query USD cost (tokens on hover)
//   - FollowupChips      — 2–3 clickable follow-up questions
//   - DataQualityBadges  — info/warn flags from local profiling
// All work in light AND dark themes.

import type { CostInfo, DataQualityFlag } from '@/lib/api'

export function CostBadge({ cost }: { cost: CostInfo | null | undefined }) {
  if (!cost || !Number.isFinite(cost.usd)) return null
  const usd = cost.usd
  const label = usd >= 1 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(4)}`
  return (
    <span
      data-testid="cost-badge"
      title={`${cost.input_tokens.toLocaleString()} input / ${cost.output_tokens.toLocaleString()} output tokens`}
      className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
    >
      <span aria-hidden>≈</span>
      {label}
    </span>
  )
}

export function FollowupChips({
  followups,
  onAsk,
  disabled,
}: {
  followups: string[] | null | undefined
  onAsk: (question: string) => void
  disabled?: boolean
}) {
  if (!followups || followups.length === 0) return null
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Suggested follow-ups
      </p>
      <div className="flex flex-wrap gap-2">
        {followups.slice(0, 3).map((f, i) => (
          <button
            key={i}
            type="button"
            data-testid="followup-chip"
            disabled={disabled}
            onClick={() => onAsk(f)}
            className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 transition hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300 dark:hover:bg-blue-900/50"
          >
            {f}
          </button>
        ))}
      </div>
    </div>
  )
}

export function DataQualityBadges({ flags }: { flags: DataQualityFlag[] | null | undefined }) {
  if (!flags || flags.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2">
      {flags.map((f, i) => {
        const warn = f.level === 'warn'
        return (
          <span
            key={i}
            data-testid="data-quality-badge"
            data-level={f.level}
            className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${
              warn
                ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300'
                : 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
            }`}
            title={warn ? 'Data-quality warning' : 'Data-quality note'}
          >
            <span aria-hidden>{warn ? '⚠' : 'ℹ'}</span>
            {f.column ? <span className="font-semibold">{f.column}:</span> : null}
            <span className="font-normal">{f.message}</span>
          </span>
        )
      })}
    </div>
  )
}
