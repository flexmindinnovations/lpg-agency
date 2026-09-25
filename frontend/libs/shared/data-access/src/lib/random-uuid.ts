/**
 * RFC 4122 v4 UUID that also works on insecure origins.
 *
 * `crypto.randomUUID()` exists only in secure contexts (HTTPS / localhost), so
 * on a plain-HTTP deployment (e.g. a bare IP before TLS is set up) calling it
 * throws inside the HTTP interceptor and no request is ever sent.
 * `crypto.getRandomValues()` is available everywhere.
 */
export function randomUuid(): string {
  const cryptoApi = globalThis.crypto;
  if (typeof cryptoApi.randomUUID === 'function') {
    return cryptoApi.randomUUID();
  }

  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'));
  return [
    hex.slice(0, 4).join(''),
    hex.slice(4, 6).join(''),
    hex.slice(6, 8).join(''),
    hex.slice(8, 10).join(''),
    hex.slice(10).join(''),
  ].join('-');
}
