'use client'

// The Phase 2 analytics-dashboard visual system, rendered ENTIRELY from the
// backend `chart_spec` (contract: spec/api.md + spec/capabilities/chart-generation.md).
//
// Self-contained: no external chart library, no CDNs — hand-rolled inline SVG
// + divs + Tailwind. Works in BOTH light and dark themes via `dark:` variants.
// Every color comes from src/lib/chartPalette.ts (assigned BY SERIES INDEX);
// every number is formatted via src/lib/formatNumber.ts.

import type { ChartSpec, ChartPanel, ChartSeries, LinePoint } from '@/lib/api'
import { formatFraction, formatKpiValue } from '@/lib/formatNumber'
import { TOTAL_ACCENT, seriesColor, colorForSeriesKey } from '@/lib/chartPalette'

export function Dashboard({ spec }: { spec: ChartSpec }) {
  return (
    <section
      data-testid="dashboard-chart"
      className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <header>
        <h3 className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100">
          {spec.title}
        </h3>
        {spec.subtitle && (
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{spec.subtitle}</p>
        )}
      </header>

      {spec.kind === 'dashboard' && <DashboardBody spec={spec} />}
      {spec.kind === 'line' && <LineChart points={spec.points ?? []} />}
      {spec.kind === 'bar' && <VerticalBars spec={spec} />}

      {spec.series.length > 0 && spec.kind !== 'line' && <Legend series={spec.series} />}
    </section>
  )
}

// ---- Dashboard kind: KPI tiles + stacked horizontal % bars ----

function DashboardBody({ spec }: { spec: ChartSpec }) {
  const panels = spec.charts ?? []
  return (
    <>
      {spec.kpis && spec.kpis.length > 0 && <KpiTiles kpis={spec.kpis} series={spec.series} />}
      {panels.length > 0 && (
        <div className={`grid gap-6 ${panels.length > 1 ? 'md:grid-cols-2' : 'grid-cols-1'}`}>
          {panels.map((panel, i) => (
            <StackedBarPanel key={i} panel={panel} series={spec.series} />
          ))}
        </div>
      )}
    </>
  )
}

function KpiTiles({ kpis, series }: { kpis: NonNullable<ChartSpec['kpis']>; series: ChartSeries[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {kpis.map((k, i) => {
        const accent = k.emphasis ? TOTAL_ACCENT : colorForSeriesKey(k.seriesKey, series)
        return (
          <div
            key={i}
            data-testid="kpi-tile"
            style={{ borderLeftColor: accent }}
            className={`rounded-lg border border-l-4 p-3 ${
              k.emphasis
                ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/40'
                : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60'
            }`}
          >
            <div className="truncate text-[11px] font-medium text-slate-500 dark:text-slate-400" title={k.label}>
              {k.label}
            </div>
            <div className="mt-1 text-2xl font-bold leading-none" style={{ color: accent }}>
              {formatKpiValue(k.value, k.format)}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// A "nice" upper bound for an axis so ticks land on round percentages.
function niceCeil(v: number): number {
  if (!Number.isFinite(v) || v <= 0) return 0.01
  const pow = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / pow
  const nice = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10
  return nice * pow
}

function StackedBarPanel({ panel, series }: { panel: ChartPanel; series: ChartSeries[] }) {
  const cats = panel.categories ?? []
  const maxVal = Math.max(...cats.map((c) => c.total), 0.0001)
  const axisMax = niceCeil(maxVal)
  const tickFracs = [0, 0.25, 0.5, 0.75, 1]

  return (
    <div data-testid="stacked-bar" className="space-y-2">
      {panel.heading && (
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {panel.heading}
        </h4>
      )}

      <div className="space-y-1.5">
        {cats.map((cat, ci) => (
          <div key={ci} className="flex items-center gap-2">
            <div
              className="w-24 shrink-0 truncate text-right text-[11px] text-slate-600 dark:text-slate-300"
              title={cat.label}
            >
              {cat.label}
            </div>
            <div className="relative h-6 flex-1">
              {/* gridlines */}
              {tickFracs.map((f) => (
                <div
                  key={f}
                  className="absolute inset-y-0 border-l border-slate-200 dark:border-slate-700"
                  style={{ left: `${f * 100}%` }}
                />
              ))}
              {/* stacked bar (widths are % of axisMax) */}
              <div className="absolute inset-y-1 left-0 flex overflow-hidden rounded-sm">
                {series.map((s, si) => {
                  const v = cat.segments?.[s.key] ?? 0
                  if (v <= 0) return null
                  return (
                    <div
                      key={s.key}
                      data-testid="bar-segment"
                      data-series={s.key}
                      style={{ width: `${(v / axisMax) * 100}%`, backgroundColor: seriesColor(si) }}
                      title={`${cat.label} · ${s.label}: ${formatFraction(v)}`}
                    />
                  )
                })}
              </div>
            </div>
            <div className="w-12 shrink-0 text-right text-[11px] font-medium tabular-nums text-slate-700 dark:text-slate-200">
              {formatFraction(cat.total)}
            </div>
          </div>
        ))}
      </div>

      {/* x-axis ticks */}
      <div className="flex items-center gap-2">
        <div className="w-24 shrink-0" />
        <div className="relative h-4 flex-1">
          {tickFracs.map((f) => (
            <span
              key={f}
              className="absolute -translate-x-1/2 text-[9px] text-slate-400 dark:text-slate-500"
              style={{ left: `${f * 100}%` }}
            >
              {formatFraction(f * axisMax)}
            </span>
          ))}
        </div>
        <div className="w-12 shrink-0" />
      </div>
      {panel.axisLabel && (
        <p className="text-center text-[10px] italic text-slate-400 dark:text-slate-500">
          {panel.axisLabel}
        </p>
      )}
    </div>
  )
}

// ---- Legend ----

function Legend({ series }: { series: ChartSeries[] }) {
  return (
    <div
      data-testid="chart-legend"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-100 pt-3 dark:border-slate-800"
    >
      {series.map((s, i) => (
        <span
          key={s.key}
          className="flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-300"
        >
          <span
            className="h-3 w-3 shrink-0 rounded-sm"
            style={{ backgroundColor: seriesColor(i) }}
          />
          {s.label}
        </span>
      ))}
    </div>
  )
}

// ---- Line kind: SVG line/area over points ----

function LineChart({ points }: { points: LinePoint[] }) {
  if (points.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-slate-400 dark:text-slate-500">
        No data points to plot.
      </p>
    )
  }

  const W = 640
  const H = 220
  const pad = { top: 12, right: 16, bottom: 28, left: 44 }
  const innerW = W - pad.left - pad.right
  const innerH = H - pad.top - pad.bottom

  // Group by series (default single series).
  const groups = new Map<string, LinePoint[]>()
  for (const p of points) {
    const key = p.series ?? '__default__'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(p)
  }
  const seriesKeys = [...groups.keys()]

  const ys = points.map((p) => p.y)
  const yMax = Math.max(...ys, 0)
  const yMin = Math.min(...ys, 0)
  const yRange = yMax - yMin || 1

  // x positions: index-based within each series (shared max length).
  const maxLen = Math.max(...[...groups.values()].map((g) => g.length))
  const xAt = (i: number) => pad.left + (maxLen <= 1 ? 0 : (i / (maxLen - 1)) * innerW)
  const yAt = (y: number) => pad.top + innerH - ((y - yMin) / yRange) * innerH

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => yMin + f * yRange)

  return (
    <div className="overflow-x-auto">
      <svg
        data-testid="line-chart"
        viewBox={`0 0 ${W} ${H}`}
        className="h-56 w-full min-w-[480px]"
        role="img"
        aria-label="Line chart"
      >
        {/* gridlines + y ticks */}
        {yTicks.map((t, i) => {
          const y = yAt(t)
          return (
            <g key={i}>
              <line
                x1={pad.left}
                x2={W - pad.right}
                y1={y}
                y2={y}
                className="stroke-slate-200 dark:stroke-slate-700"
                strokeWidth={1}
              />
              <text
                x={pad.left - 6}
                y={y + 3}
                textAnchor="end"
                className="fill-slate-400 text-[9px] dark:fill-slate-500"
              >
                {formatFraction(t)}
              </text>
            </g>
          )
        })}

        {seriesKeys.map((key, si) => {
          const g = groups.get(key)!
          const color = seriesColor(si)
          const line = g.map((p, i) => `${xAt(i)},${yAt(p.y)}`).join(' ')
          const area = `${xAt(0)},${yAt(yMin)} ${line} ${xAt(g.length - 1)},${yAt(yMin)}`
          return (
            <g key={key}>
              <polygon points={area} fill={color} opacity={0.12} />
              <polyline points={line} fill="none" stroke={color} strokeWidth={2} />
              {g.map((p, i) => (
                <circle key={i} cx={xAt(i)} cy={yAt(p.y)} r={2.5} fill={color} />
              ))}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ---- Bar kind: vertical bars ----
//
// Prefers `points` (x/y) when present; otherwise flattens the first chart
// panel's categories into vertical bars so a plain "bar" spec still renders.
function VerticalBars({ spec }: { spec: ChartSpec }) {
  const bars: { label: string; value: number }[] =
    spec.points && spec.points.length > 0
      ? spec.points.map((p) => ({ label: String(p.x), value: p.y }))
      : (spec.charts?.[0]?.categories ?? []).map((c) => ({ label: c.label, value: c.total }))

  if (bars.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-slate-400 dark:text-slate-500">
        Nothing to chart.
      </p>
    )
  }

  const axisMax = niceCeil(Math.max(...bars.map((b) => b.value), 0.0001))

  return (
    <div data-testid="vertical-bars" className="flex h-48 items-end gap-2 border-b border-l border-slate-200 pl-2 dark:border-slate-700">
      {bars.map((b, i) => (
        <div key={i} className="flex flex-1 flex-col items-center justify-end gap-1" title={`${b.label}: ${formatFraction(b.value)}`}>
          <div
            data-testid="bar-segment"
            className="w-full rounded-t-sm"
            style={{ height: `${(b.value / axisMax) * 100}%`, backgroundColor: seriesColor(i) }}
          />
          <span className="w-full truncate text-center text-[9px] text-slate-500 dark:text-slate-400">
            {b.label}
          </span>
        </div>
      ))}
    </div>
  )
}
