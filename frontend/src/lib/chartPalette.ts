// Single source of truth for the analytics-dashboard color system.
//
// Colors are assigned to series BY INDEX (0..3), matching the authoritative
// palette in spec/capabilities/chart-generation.md and spec/ui.md. Tiles,
// bar segments, and the legend all read from here so nothing re-derives a
// color from a label. The palette is chosen to read cleanly in BOTH light
// and dark themes.

// Ordered series palette — index 0..3 (wraps for >4 series).
export const SERIES_PALETTE = [
  '#1e40af', // index 0 — dark blue  (e.g. Dynamic QR)
  '#ea580c', // index 1 — orange     (e.g. Initiate Link)
  '#64748b', // index 2 — slate/grey  (e.g. Static QR)
  '#b91c1c', // index 3 — dark red    (e.g. Cheque + DD)
] as const

// Accent for the emphasized "total" KPI tile.
export const TOTAL_ACCENT = '#16a34a' // green

/** Color for a series by its stable index; wraps if there are >4 series. */
export function seriesColor(index: number): string {
  if (index < 0) return SERIES_PALETTE[0]
  return SERIES_PALETTE[index % SERIES_PALETTE.length]
}

/**
 * Resolve a series color from its key, given the ordered series list.
 * Falls back to a neutral slate when the key is unknown/null.
 */
export function colorForSeriesKey(
  seriesKey: string | null | undefined,
  series: { key: string }[],
): string {
  if (!seriesKey) return '#64748b'
  const idx = series.findIndex((s) => s.key === seriesKey)
  return idx >= 0 ? seriesColor(idx) : '#64748b'
}
