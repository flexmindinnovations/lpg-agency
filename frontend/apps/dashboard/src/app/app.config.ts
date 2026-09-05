import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideRouter, withComponentInputBinding, withViewTransitions } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { providePrimeNG } from 'primeng/config';
import {
  authInterceptor,
  correlationIdInterceptor,
  problemDetailsInterceptor,
  provideApiConfiguration,
} from '@lpg/shared/data-access';
import { LpgPrimeNgPreset } from '@lpg/shared/design-tokens';
import { appRoutes } from './app.routes';
import { PRIME_NG_LICENSE_KEY } from './prime-license';
import { environment } from '../environments/environment';
import { MessageService, ConfirmationService } from 'primeng/api';
import { PERMISSION_CHECKER, API_BASE_URL } from '@lpg/shared/util';
import { inject } from '@angular/core';
import { AuthService } from '@lpg/shared/data-access';


export const appConfig: ApplicationConfig = {
  providers: [
    {
      provide: PERMISSION_CHECKER,
      useFactory: () => inject(AuthService).principal,
    },
    MessageService,
    ConfirmationService,
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      appRoutes,
      withComponentInputBinding(),
      // Native View Transitions API cross-fade between routes (Phase 29
      // Stage 1). Progressive enhancement — a no-op in browsers without
      // `document.startViewTransition`. The actual animation is styled on
      // `::view-transition-old/new(root)` in styles.css; `skipInitial
      // Transition` keeps the first paint from animating; the hook below
      // skips it entirely under `prefers-reduced-motion` (the styled
      // durations also collapse to 0 there — belt and braces).
      withViewTransitions({
        skipInitialTransition: true,
        onViewTransitionCreated: ({ transition }) => {
          if (
            typeof matchMedia === 'function' &&
            matchMedia('(prefers-reduced-motion: reduce)').matches
          ) {
            transition.skipTransition();
          }
        },
      }),
    ),
    // Backend root URL, swapped per build configuration via `fileReplacements`
    // (`apps/dashboard/project.json`) — see `src/environments/environment.ts`.
    provideApiConfiguration(environment.apiUrl),
    // Same value, `type:util`-reachable DI surface for hand-written
    // `type:data-access` libs (e.g. `reporting/data-access`) that cannot
    // depend on `@lpg/shared/data-access`'s `ApiConfiguration` — see
    // `API_BASE_URL`'s own docstring.
    { provide: API_BASE_URL, useValue: environment.apiUrl },
    provideHttpClient(
      // Order matters, and it's the reverse of what it looks like: Angular's
      // interceptor chain nests so the *last* array entry sits closest to
      // the real HTTP call, meaning its response-side operators (catchError
      // etc.) run FIRST on the way back — before any earlier entry's. So
      // authInterceptor must be last, not problemDetailsInterceptor: it
      // needs to see the raw HttpErrorResponse from a 401 to run its
      // refresh-and-retry / session-expired-dialog logic (the `error
      // instanceof HttpErrorResponse` check in auth.interceptor.ts).
      // Putting problemDetailsInterceptor closer to the backend converts
      // every error to a plain AppError before authInterceptor ever sees
      // it, silently disabling that check — this was a real, live bug
      // (verified: a genuine 401 in the network tab produced no
      // session-expired dialog) caused by exactly this ordering being
      // backwards. correlationIdInterceptor is request-only (no response
      // pipe), so its position relative to the other two doesn't matter.
      withInterceptors([correlationIdInterceptor, problemDetailsInterceptor, authInterceptor]),
    ),
    // Overlay/transition animations (Dialog, Drawer, Toast, dropdowns) need
    // Angular's animation system. Loaded async so it is not in the initial
    // bundle for routes that never touch an overlay component. (Route
    // transitions do NOT use this — they run on the native View Transitions
    // API via `withViewTransitions()` above.)
    provideAnimationsAsync(),
    // PrimeNG (ADR-028, ADR-020 amendment): primary component library.
    // `LpgPrimeNgPreset` is the only place PrimeNG's own colours are ever
    // set — every value in it is `var(--token-name)` or derived from one
    // (`libs/shared/design-tokens/src/lib/primeng-preset.ts`). No PrimeNG
    // component in this codebase should ever need a manual colour override;
    // if one seems to, the preset is the place to fix it, not the component.
    providePrimeNG({
      // Never hardcode the real key (ADR-020's AG Grid rule applies equally
      // here). `prime-license.ts` is git-ignored; see
      // `prime-license.example.ts` for how to supply a real key locally/CI.
      license: PRIME_NG_LICENSE_KEY,
      theme: {
        preset: LpgPrimeNgPreset,
        options: {
          // Matches ThemeService's own attribute exactly — PrimeNG's dark
          // detection must follow the in-app theme toggle, not just the OS
          // `prefers-color-scheme` ("system", PrimeNG's default) — a user
          // picking "Dark" in-app would otherwise still see PrimeNG's light
          // defaults for anything this preset doesn't explicitly override.
          darkModeSelector: '[data-theme="dark"]',
        },
      },
    }),
  ],
};
