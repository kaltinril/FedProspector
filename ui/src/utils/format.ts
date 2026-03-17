/**
 * Shared formatting utilities for detail pages.
 */

interface PlaceOfPerformanceFields {
  popCity?: string | null;
  popState?: string | null;
  popZip?: string | null;
  popCountry?: string | null;
}

/**
 * Build a human-readable place-of-performance string from city/state/zip/country fields.
 *
 * @param record - Any object with optional popCity, popState, popZip, popCountry fields.
 * @param fallback - Value to return when no POP fields are populated. Defaults to null.
 * @returns Formatted string like "Springfield, VA, 22150" or the fallback value.
 */
export function buildPlaceOfPerformance(
  record: PlaceOfPerformanceFields,
  fallback?: string,
): string | null {
  const parts: string[] = [];
  if (record.popCity) parts.push(record.popCity);
  if (record.popState) parts.push(record.popState);
  if (record.popZip) parts.push(record.popZip);
  if (record.popCountry && record.popCountry !== 'USA' && record.popCountry !== 'US') {
    parts.push(record.popCountry);
  }
  return parts.length > 0 ? parts.join(', ') : (fallback ?? null);
}
