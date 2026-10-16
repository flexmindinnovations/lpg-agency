import { isStaleAssetError, reloadOnceForStaleAsset } from './hard-navigate';

describe('isStaleAssetError', () => {
  it.each([
    'Failed to fetch dynamically imported module: https://x/chunk-ABC.js',
    'error loading dynamically imported module',
    'Importing a module script failed.',
    'Loading chunk 42 failed.',
    'Failed to load module script: Expected a JavaScript-or-Wasm module script but the server responded with a MIME type of "text/html".',
    "SyntaxError: Unexpected token '<'",
    'Expected a JavaScript module script but the server responded with a MIME type of "text/html": not a valid JavaScript MIME type',
  ])('recognises: %s', (message) => {
    expect(isStaleAssetError(new Error(message))).toBe(true);
  });

  it('recognises a ChunkLoadError by name', () => {
    const error = new Error('boom');
    error.name = 'ChunkLoadError';
    expect(isStaleAssetError(error)).toBe(true);
  });

  it('ignores ordinary navigation failures', () => {
    expect(isStaleAssetError(new Error('Cannot match any routes. URL Segment: x'))).toBe(false);
    expect(isStaleAssetError(undefined)).toBe(false);
  });
});

describe('reloadOnceForStaleAsset', () => {
  const fakeStorage = () => {
    const data = new Map<string, string>();
    return {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
    };
  };

  it('reloads the target the first time', () => {
    const go = jest.fn();

    expect(reloadOnceForStaleAsset('/orders', go, 1_000, fakeStorage())).toBe(true);
    expect(go).toHaveBeenCalledWith('/orders');
  });

  it('does not reload again within 15 seconds, so a broken deploy cannot loop', () => {
    const go = jest.fn();
    const storage = fakeStorage();
    reloadOnceForStaleAsset('/orders', go, 1_000, storage);

    expect(reloadOnceForStaleAsset('/orders', go, 10_000, storage)).toBe(false);
    expect(go).toHaveBeenCalledTimes(1);
  });

  it('reloads again once the window has passed', () => {
    const go = jest.fn();
    const storage = fakeStorage();
    reloadOnceForStaleAsset('/orders', go, 1_000, storage);

    expect(reloadOnceForStaleAsset('/customers', go, 20_000, storage)).toBe(true);
    expect(go).toHaveBeenLastCalledWith('/customers');
  });

  it('still reloads when session storage is unavailable', () => {
    const go = jest.fn();

    expect(reloadOnceForStaleAsset('/orders', go, 1_000, null)).toBe(true);
  });
});
