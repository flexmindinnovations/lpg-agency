import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

/**
 * Blocks navigation into the shell until a session exists.
 *
 * An in-memory access token surviving from an earlier navigation is enough
 * to proceed immediately. On a fresh page load there is none — the store
 * lost it on reload by design (`AuthTokenStore`'s docstring) — so this
 * falls back to `AuthService.ensureSessionRestored()`, which redeems the
 * `HttpOnly` refresh cookie silently (deduped against any other guard
 * doing the same for this same navigation — see that method's own
 * docstring for why a bare `restoreSession()` call here isn't safe). Only
 * a failure there (no valid cookie either) redirects to `/login`,
 * preserving the attempted URL as a `redirectTo` query param.
 */
export const authGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService
    .ensureSessionRestored()
    .pipe(
      map((restored) =>
        restored
          ? true
          : router.createUrlTree(['/login'], { queryParams: { redirectTo: state.url } }),
      ),
    );
};
