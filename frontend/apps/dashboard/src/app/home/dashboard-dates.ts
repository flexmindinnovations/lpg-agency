/**
 * Calendar-day helpers for the dashboard. Business days are IST (the agency's
 * clock), so "today" is the IST date, not the browser's, and day arithmetic
 * is done on plain `YYYY-MM-DD` strings so it never shifts with a time zone.
 */

const IST = 'Asia/Kolkata';

/** `YYYY-MM-DD` of the given instant in IST. */
export function istDate(at: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: IST,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(at);
}

function toUtcMs(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}

/** `iso` moved by `days` (negative goes back). */
export function addDays(iso: string, days: number): string {
  return new Date(toUtcMs(iso) + days * 86_400_000).toISOString().slice(0, 10);
}

/** Every date from `start` to `end` inclusive. */
export function dateRange(start: string, end: string): string[] {
  const out: string[] = [];
  for (let d = start; d <= end; d = addDays(d, 1)) out.push(d);
  return out;
}

const SHORT = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' });

/** "12 Nov". */
export function shortDate(iso: string): string {
  return SHORT.format(new Date(toUtcMs(iso)));
}
