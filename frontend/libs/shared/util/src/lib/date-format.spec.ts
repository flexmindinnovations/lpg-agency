import {
  LpgDatePipe,
  LpgDateTimePipe,
  formatDisplayDate,
  formatDisplayDateTime,
  parseDisplayDate,
  toIsoDate,
} from './date-format';

describe('date-format', () => {
  it('formats an instant as an IST calendar date', () => {
    // 20:00 UTC on the 19th is 01:30 IST on the 20th.
    expect(formatDisplayDate('2026-10-19T20:00:00Z')).toBe('20 Oct 2026');
  });

  it('never shifts a date-only value', () => {
    expect(formatDisplayDate('2026-10-20')).toBe('20 Oct 2026');
    expect(formatDisplayDateTime('2026-10-20')).toBe('20 Oct 2026');
  });

  it('formats a date-time in IST, 24-hour', () => {
    expect(formatDisplayDateTime('2026-10-20T04:39:00Z')).toBe('20 Oct 2026, 10:09');
    expect(formatDisplayDateTime('2026-10-20T12:30:00Z')).toBe('20 Oct 2026, 18:00');
  });

  it('returns empty for empty input and the raw value when unparseable', () => {
    expect(formatDisplayDate(null)).toBe('');
    expect(formatDisplayDate('')).toBe('');
    expect(formatDisplayDateTime(undefined)).toBe('');
    expect(formatDisplayDate('not a date')).toBe('not a date');
  });

  it('parses dd/mm/yyyy day-first and rejects impossible days', () => {
    const date = parseDisplayDate('15/06/1985');
    expect(date && toIsoDate(date)).toBe('1985-06-15');
    expect(parseDisplayDate('01-01-2010') && toIsoDate(parseDisplayDate('01-01-2010'))).toBe(
      '2010-01-01',
    );
    expect(parseDisplayDate('31/02/2026')).toBeNull();
    expect(parseDisplayDate('06/15/1985')).toBeNull();
    expect(parseDisplayDate('1985-06-15')).toBeNull();
  });

  it('serialises a picked local date without a UTC shift', () => {
    expect(toIsoDate(new Date(2026, 9, 20))).toBe('2026-10-20');
    expect(toIsoDate(null)).toBeNull();
  });

  it('exposes the same formats as pipes', () => {
    expect(new LpgDatePipe().transform('2026-10-20')).toBe('20 Oct 2026');
    expect(new LpgDateTimePipe().transform('2026-10-20T04:39:00Z')).toBe('20 Oct 2026, 10:09');
  });
});
