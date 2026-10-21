import { istDate, loadErrorMessage } from './reporting.store';

describe('loadErrorMessage', () => {
  it('reads the normalised API error detail', () => {
    expect(loadErrorMessage({ errorCode: 'INTERNAL', detail: 'Server error.' })).toBe(
      'Server error.',
    );
  });

  it('names a network failure and never returns empty', () => {
    expect(loadErrorMessage({ errorCode: 'NETWORK', detail: '', isNetworkError: true })).toContain(
      'Cannot reach the server',
    );
    expect(loadErrorMessage({})).toBe('The report could not be loaded. Please try again.');
    expect(loadErrorMessage(null)).toBe('The report could not be loaded. Please try again.');
  });
});

describe('istDate', () => {
  afterEach(() => jest.useRealTimers());

  it('uses the Indian calendar day, not the UTC one', () => {
    // 20:00 UTC on 19 Oct is already 01:30 on 20 Oct in India.
    jest.useFakeTimers().setSystemTime(new Date('2026-10-19T20:00:00Z'));
    expect(istDate()).toBe('2026-10-20');
    expect(istDate(-29)).toBe('2026-09-21');
  });
});
