/**
 * Small display formatters for data-grid `valueFormatter`s and templates.
 * `Intl` directly — no locale-data registration, works in every browser.
 */

const NBSP_RE = /\s/g;

export function formatCurrencyInr(value: unknown): string {
  if (value == null || value === '') return '';
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  })
    .format(n)
    .replace(NBSP_RE, ' ');
}

export function formatReportDate(value: unknown): string {
  if (value == null || value === '') return '';
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(d);
}

/** `value` is a ratio (0–1); rendered as a percentage. */
export function formatPercent(value: unknown, digits = 2): string {
  if (value == null || value === '') return '';
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return new Intl.NumberFormat('en-IN', {
    style: 'percent',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

export function formatDecimal(value: unknown, digits = 1): string {
  if (value == null || value === '') return '';
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(n);
}
