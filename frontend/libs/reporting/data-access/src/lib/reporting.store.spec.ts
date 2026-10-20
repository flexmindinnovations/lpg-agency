import { istDate } from './reporting.store';

describe('istDate', () => {
  afterEach(() => jest.useRealTimers());

  it('uses the Indian calendar day, not the UTC one', () => {
    // 20:00 UTC on 19 Oct is already 01:30 on 20 Oct in India.
    jest.useFakeTimers().setSystemTime(new Date('2026-10-19T20:00:00Z'));
    expect(istDate()).toBe('2026-10-20');
    expect(istDate(-29)).toBe('2026-09-21');
  });
});
