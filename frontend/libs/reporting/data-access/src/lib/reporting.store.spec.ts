import { loadErrorMessage } from './reporting.store';

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
