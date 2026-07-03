// Display formatting for computed numeric result values.
//
// Backend returns raw numbers (long-decimal floats, e.g. 0.1783456789 or
// 11785000.0). For display we:
//   - render clear proportions in "percent-like" columns as e.g. 17.8%
//   - group large numbers with comma thousands separators (11,785,000)
//   - round to at most 2 decimals; show integers with no decimals
//
// Detection is deliberately pragmatic — driven by the column name plus the
// value's magnitude — not a general-purpose type system.

const GROUPED = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

const PERCENT = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

// Column names whose values are naturally proportions/percentages.
const PERCENT_HINT = /(ratio|rate|pct|percent|proportion|share|%)/i

function looksLikePercentColumn(columnName?: string): boolean {
  return !!columnName && PERCENT_HINT.test(columnName)
}

/** Format a single numeric value, optionally using its column name as a hint. */
export function formatNumericValue(value: number, columnName?: string): string {
  if (!Number.isFinite(value)) return String(value)

  // A clear proportion in a percent-like column (|v| <= 1) renders as a percent.
  if (looksLikePercentColumn(columnName) && Math.abs(value) <= 1) {
    return PERCENT.format(value)
  }

  // Integers show with no decimals; everything else is grouped + trimmed to 2dp.
  return GROUPED.format(value)
}

/**
 * Format an arbitrary result-table / answer cell for display.
 * Non-numeric cells (strings, booleans, null) pass through unchanged.
 */
export function formatCell(
  cell: string | number | boolean | null,
  columnName?: string,
): string {
  if (cell === null || cell === undefined) return '—'
  if (typeof cell === 'number') return formatNumericValue(cell, columnName)

  // Numeric strings that the backend serialised as text still get formatted.
  if (typeof cell === 'string' && cell.trim() !== '' && !Number.isNaN(Number(cell))) {
    return formatNumericValue(Number(cell), columnName)
  }

  return String(cell)
}
