import { Pipe, PipeTransform } from '@angular/core';

/**
 * The one date / date-time display format for the whole dashboard (QA DA-31,
 * DO-08): "20 Oct 2026" and "20 Oct 2026, 10:09", always in India Standard
 * Time, whatever the browser's own locale or time zone is. Before this,
 * screens used `toLocaleDateString()` (US "10/17/2026" in an en-US Chrome),
 * Angular's `date` pipe ("Oct 17, 2026") and ISO strings side by side.
 *
 * Use these functions in grid `valueFormatter`s and component code, and the
 * `lpgDate` / `lpgDateTime` pipes in templates. Date inputs use
 * `DATE_INPUT_FORMAT` (set app-wide on PrimeNG's DatePicker in `app.config.ts`)
 * so a typed "15/06/1985" is read day-first.
 */

/** The agency's business time zone. Every displayed time is in IST. */
export const DISPLAY_TIME_ZONE = 'Asia/Kolkata';

/** PrimeNG DatePicker `dateFormat` for every date input: dd/mm/yyyy. */
export const DATE_INPUT_FORMAT = 'dd/mm/yy';

/** Placeholder shown in empty date inputs, matching `DATE_INPUT_FORMAT`. */
export const DATE_INPUT_PLACEHOLDER = 'dd/mm/yyyy';

/** A calendar date with no time ("2026-10-20"), as the API sends `date` fields. */
const ISO_DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

const DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  timeZone: DISPLAY_TIME_ZONE,
});

/** Same pattern for calendar dates, which have no time zone to convert from. */
const CALENDAR_DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
});

const TIME_FORMAT = new Intl.DateTimeFormat('en-IN', {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: DISPLAY_TIME_ZONE,
});

type DateInput = Date | string | number | null | undefined;

/** Parse an API value into a `Date`; `null` when empty or unparseable. */
export function toDate(value: unknown): Date | null {
  if (value == null || value === '') return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value !== 'string' && typeof value !== 'number') return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * "20 Oct 2026". A date-only string ("2026-10-20") is shown as that calendar
 * day, never shifted by a time-zone conversion. Empty input gives `''`;
 * an unparseable value is returned as-is so bad data stays visible.
 */
export function formatDisplayDate(value: DateInput | unknown): string {
  if (value == null || value === '') return '';
  if (typeof value === 'string') {
    const match = ISO_DATE_ONLY.exec(value);
    if (match) {
      const [, y, m, d] = match;
      return CALENDAR_DATE_FORMAT.format(new Date(Date.UTC(+y, +m - 1, +d)));
    }
  }
  const date = toDate(value);
  return date ? DATE_FORMAT.format(date) : String(value);
}

/** "20 Oct 2026, 10:09" (24-hour, IST). A date-only string gets no time. */
export function formatDisplayDateTime(value: DateInput | unknown): string {
  if (typeof value === 'string' && ISO_DATE_ONLY.test(value)) return formatDisplayDate(value);
  const date = toDate(value);
  if (!date) return value == null || value === '' ? '' : String(value);
  return `${DATE_FORMAT.format(date)}, ${TIME_FORMAT.format(date)}`;
}

/**
 * Parse a typed "dd/mm/yyyy" (also "dd-mm-yyyy" or "dd.mm.yyyy") into a local
 * `Date`. Returns `null` for anything that is not a real calendar day, so a
 * caller can show "Enter the date as dd/mm/yyyy" instead of dropping it.
 */
export function parseDisplayDate(text: string): Date | null {
  const match = /^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*$/.exec(text ?? '');
  if (!match) return null;
  const [day, month, year] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(year, month - 1, day);
  const valid =
    date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
  return valid ? date : null;
}

/**
 * A picked `Date` as the API's `date` field ("2026-10-20"), using the day the
 * user picked rather than its UTC instant (`toISOString()` gives the previous
 * day for an IST midnight).
 */
export function toIsoDate(value: Date | null | undefined): string | null {
  if (!value || Number.isNaN(value.getTime())) return null;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

/** `{{ order.created_at | lpgDate }}` → "20 Oct 2026". */
@Pipe({ name: 'lpgDate', standalone: true })
export class LpgDatePipe implements PipeTransform {
  transform(value: unknown): string {
    return formatDisplayDate(value);
  }
}

/** `{{ order.created_at | lpgDateTime }}` → "20 Oct 2026, 10:09". */
@Pipe({ name: 'lpgDateTime', standalone: true })
export class LpgDateTimePipe implements PipeTransform {
  transform(value: unknown): string {
    return formatDisplayDateTime(value);
  }
}
