import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { map } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthTokenStore } from './auth-token.store';

/**
 * Route-level gate for the `/platform` shell tree — the Platform Console
 * sibling of `permissionGuard`, checked against `role` rather than a
 * permission code: D-01 makes `super_admin` the only role with no tenant,
 * so this is the client-side mirror of `JwtPlatformPrincipalResolver`'s own
 * `role != "super_admin"` rejection. A UI convenience only — every
 * `/platform/*` endpoint re-enforces this server-side regardless.
 *
 * Calls `AuthService.ensureSessionRestored()` itself rather than trusting
 * `authGuard` to have already run — see that method's own docstring: on a
 * hard reload, a later guard in the same `canActivate` array is not
 * guaranteed to see a hydrated principal just because an earlier guard
 * kicked off the restore. Cheap no-op once a session already exists.
 */
export const platformAuthGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const tokenStore = inject(AuthTokenStore);
  const router = inject(Router);

  return authService
    .ensureSessionRestored()
    .pipe(
      map(() =>
        tokenStore.principal()?.role === 'super_admin' ? true : router.createUrlTree(['/']),
      ),
    );
};
