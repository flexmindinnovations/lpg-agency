import { randomUuid } from './random-uuid';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('randomUuid', () => {
  const original = globalThis.crypto.randomUUID;

  afterEach(() => {
    Object.defineProperty(globalThis.crypto, 'randomUUID', {
      value: original,
      configurable: true,
      writable: true,
    });
  });

  it('returns a v4 UUID when crypto.randomUUID is available', () => {
    expect(randomUuid()).toMatch(UUID_V4);
  });

  it('falls back to getRandomValues on insecure origins, where randomUUID is undefined', () => {
    Object.defineProperty(globalThis.crypto, 'randomUUID', {
      value: undefined,
      configurable: true,
      writable: true,
    });

    const first = randomUuid();
    expect(first).toMatch(UUID_V4);
    expect(randomUuid()).not.toBe(first);
  });
});
