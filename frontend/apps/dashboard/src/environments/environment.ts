import type { Environment } from './environment.model';

/**
 * Default (local development) environment. Swapped for `environment.prod.ts`
 * in the `production` build configuration via `fileReplacements`
 * (`apps/dashboard/project.json`) — Angular's own established mechanism for
 * this, not a bespoke one.
 *
 * `apiUrl` is absolute here because the backend's local dev instance
 * (`README.md`: `uv run uvicorn lpg.api.app:app --reload`) runs on its own
 * port, not behind the Angular dev server. The backend's `LPG_CORS_ORIGINS`
 * dev default already allows `http://localhost:4200` for exactly this.
 *
 * **No `/api/v1` suffix** — `provideApiConfiguration(environment.apiUrl)`
 * feeds `ApiConfiguration.rootUrl`, which every generated client function
 * concatenates with its own `.PATH` constant; those paths already carry the
 * full mounted path (e.g. `/api/v1/auth/login`, since that's what
 * `settings.api_v1_prefix` actually mounts and what FastAPI's OpenAPI spec
 * reports). Appending `/api/v1` here doubled it into
 * `/api/v1/api/v1/auth/login` — found via a real login attempt against a
 * live backend, not caught by any build/lint/test check because nothing
 * type-checks a URL string's runtime correctness.
 */
export const environment: Environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
};
