import { InjectionToken } from '@angular/core';

/**
 * The backend's root URL (e.g. `http://localhost:8000` in dev, `''` same-
 * origin in prod — see `environment.apiUrl`'s own docstring).
 *
 * `type:data-access` libs may only depend on `type:util` libs
 * (`@nx/enforce-module-boundaries`), so this lives here rather than being
 * read off `@lpg/shared/data-access`'s `ApiConfiguration`, which every
 * *generated* API client uses instead. Both are provided from the same
 * `environment.apiUrl` value in `app.config.ts` — one DI surface for
 * generated clients, one for hand-written ones that can't reach it.
 */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL');
