import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideRouter, withComponentInputBinding } from '@angular/router';
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

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(appRoutes, withComponentInputBinding()),
    // Backend root URL, swapped per build configuration via `fileReplacements`
    // (`apps/dashboard/project.json`) — see `src/environments/environment.ts`.
    provideApiConfiguration(environment.apiUrl),
    provideHttpClient(
      // Order matters: correlation ID is attached on the way out, the
      // bearer token is attached (and a 401 gets one silent
      // refresh-and-retry) next, and Problem Details is translated on the
      // way back — after auth has had its chance to recover a request.
      withInterceptors([correlationIdInterceptor, authInterceptor, problemDetailsInterceptor]),
    ),
    // Overlay/transition animations (Dialog, Drawer, Toast, dropdowns) need
    // Angular's animation system. Loaded async so it is not in the initial
    // bundle for routes that never touch an overlay component.
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
