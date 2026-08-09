import type { Environment } from './environment.model';

/**
 * Production environment. `apiUrl` is deliberately a same-origin relative
 * path, not an absolute domain — hosting topology (ADR-022) and therefore
 * the real production domain are still undecided. A relative path assumes
 * the SPA and API are served from the same origin (directly, or behind a
 * reverse proxy/edge routing `/api/*` to the backend) — the least
 * committal choice that doesn't require guessing infrastructure nobody has
 * decided yet. Revisit when ADR-022 resolves.
 */
export const environment: Environment = {
  production: true,
  apiUrl: '/api/v1',
};
