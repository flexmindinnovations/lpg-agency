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
 */
export const environment: Environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api/v1',
};
