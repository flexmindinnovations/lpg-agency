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
 * a failure there (no valid cookie either) redirects to `/login`.
 *
 * Deliberately does *not* preserve the attempted URL as a `redirectTo`
 * query param — this guard cannot tell "session just expired mid-use"
 * apart from "never authenticated, deep link" (both look identical after
 * a fresh navigation/reload; no in-memory flag survives either case), so
 * every forced re-login now lands on the role-based smart default
 * (`login-page.ts`'s `submit()`) instead of bouncing back to whatever
 * page triggered this guard.
 */
export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService
    .ensureSessionRestored()
    .pipe(map((restored) => (restored ? true : router.createUrlTree(['/login']))));
};
