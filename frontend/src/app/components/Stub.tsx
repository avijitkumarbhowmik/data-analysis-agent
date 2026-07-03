// A clearly-labelled, visibly-disabled "coming soon" surface.
//
// These exist so the user sees the full product vision in Phase 1 without ever
// mistaking a not-yet-built feature for a bug. Every stub carries a phase badge
// and is non-interactive.

interface StubProps {
  title: string
  phase: 'Phase 2' | 'Phase 3'
  children?: React.ReactNode
  compact?: boolean
}

export function Stub({ title, phase, children, compact }: StubProps) {
  return (
    <div
      data-testid="stub"
      data-stub-title={title}
      aria-disabled="true"
      className={`pointer-events-none select-none rounded-xl border border-dashed border-gray-300 bg-gray-50/70 ${
        compact ? 'p-3' : 'p-4'
      } text-gray-400`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className={`font-medium ${compact ? 'text-xs' : 'text-sm'} text-gray-500`}>
          {title}
        </span>
        <span className="shrink-0 rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          {phase} · coming soon
        </span>
      </div>
      {children && <div className="mt-2 text-xs text-gray-400">{children}</div>}
    </div>
  )
}

// A disabled button-shaped stub for inline use (e.g. Export, Save-derived).
export function StubButton({ label, phase }: { label: string; phase: 'Phase 2' | 'Phase 3' }) {
  return (
    <button
      type="button"
      disabled
      aria-disabled="true"
      data-testid="stub-button"
      title={`${label} — ${phase}, coming soon`}
      className="pointer-events-none inline-flex cursor-not-allowed items-center gap-1.5 rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-400"
    >
      {label}
      <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-gray-500">
        {phase}
      </span>
    </button>
  )
}
