/**
 * Format a number as US currency.
 * @param compact - If true, abbreviate large values (e.g., $1.2M).
 */
export function formatCurrency(
  value: number | null | undefined,
  compact = false,
): string {
  if (value == null) return '--';
  if (compact) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Format a NAICS code for display.
 * Currently returns the code as-is. A future enhancement could map codes to descriptions.
 */
export function formatNaicsCode(code: string): string {
  return code;
}

/**
 * Format a number with thousand separators.
 */
export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '--';
  return new Intl.NumberFormat('en-US').format(value);
}

/**
 * Format a number as a percentage.
 */
export function formatPercent(
  value: number | null | undefined,
  decimals = 1,
): string {
  if (value == null) return '--';
  return `${value.toFixed(decimals)}%`;
}
