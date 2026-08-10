import type { Environment } from './environment.model';

/**
 * Production environment. `apiUrl` is deliberately a same-origin empty
 * path, not an absolute domain — hosting topology (ADR-022) and therefore
 * the real production domain are still undecided. An empty root assumes
 * the SPA and API are served from the same origin (directly, or behind a
 * reverse proxy/edge routing `/api/*` to the backend) — the least
 * committal choice that doesn't require guessing infrastructure nobody has
 * decided yet. Revisit when ADR-022 resolves.
 *
 * **No `/api/v1` suffix** — see `environment.ts`'s matching note. Every
 * generated client function's own `.PATH` constant already carries the full
 * mounted path (e.g. `/api/v1/auth/login`); `rootUrl` is just the origin
 * (here, empty = same-origin) that gets prepended to it.
 */
export const environment: Environment = {
  production: true,
  apiUrl: '',
};
