import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { AuthTokenStore } from './auth-token.store';

/**
 * Route-level permission gate, checked against the claims embedded in the
 * access token at issuance (`docs/data/17-api-security.md` §4: "fast,
 * no-database-round-trip authorization"). This is a UI convenience only —
 * the API re-enforces every permission server-side regardless
 * (`require_permission`/`require_live_permission`), so a stale or bypassed
 * client check can never itself grant access to data.
 *
 * `authGuard` must run first on any route using this — it assumes a
 * resolved principal already exists.
 */
export function permissionGuard(permissionCode: string): CanActivateFn {
  return () => {
    const tokenStore = inject(AuthTokenStore);
    const router = inject(Router);

    const principal = tokenStore.principal();
    if (principal?.permissions.has(permissionCode)) {
      return true;
    }
    return router.createUrlTree(['/']);
  };
}
