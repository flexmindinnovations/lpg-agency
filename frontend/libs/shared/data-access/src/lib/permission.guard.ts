import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { map } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthTokenStore } from './auth-token.store';

/**
 * Route-level permission gate, checked against the claims embedded in the
 * access token at issuance (`docs/data/17-api-security.md` §4: "fast,
 * no-database-round-trip authorization"). This is a UI convenience only —
 * the API re-enforces every permission server-side regardless
 * (`require_permission`/`require_live_permission`), so a stale or bypassed
 * client check can never itself grant access to data.
 *
 * Calls `AuthService.ensureSessionRestored()` itself rather than trusting
 * `authGuard` on a parent route to have already resolved one — see that
 * method's own docstring: verified live that a child route's guard can run
 * before a parent's async `authGuard` finishes hydrating the principal, so
 * every guard reading `tokenStore.principal()` synchronously must ensure
 * that itself. Cheap no-op once a session already exists.
 */
export function permissionGuard(permissionCode: string): CanActivateFn {
  return () => {
    const authService = inject(AuthService);
    const tokenStore = inject(AuthTokenStore);
    const router = inject(Router);

    return authService
      .ensureSessionRestored()
      .pipe(
        map(() =>
          tokenStore.principal()?.permissions.has(permissionCode)
            ? true
            : router.createUrlTree(['/']),
        ),
      );
  };
}
