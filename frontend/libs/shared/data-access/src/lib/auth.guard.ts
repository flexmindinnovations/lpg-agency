import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { map } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthTokenStore } from './auth-token.store';

/**
 * Blocks navigation into the shell until a session exists.
 *
 * An in-memory access token surviving from an earlier navigation is enough
 * to proceed immediately. On a fresh page load there is none — the store
 * lost it on reload by design (`AuthTokenStore`'s docstring) — so this
 * falls back to `AuthService.restoreSession()`, which redeems the
 * `HttpOnly` refresh cookie silently. Only a failure there (no valid
 * cookie either) redirects to `/login`, preserving the attempted URL as a
 * `redirectTo` query param.
 */
export const authGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const tokenStore = inject(AuthTokenStore);
  const router = inject(Router);

  if (tokenStore.accessToken()) {
    return true;
  }

  return authService
    .restoreSession()
    .pipe(
      map((restored) =>
        restored
          ? true
          : router.createUrlTree(['/login'], { queryParams: { redirectTo: state.url } }),
      ),
    );
};
