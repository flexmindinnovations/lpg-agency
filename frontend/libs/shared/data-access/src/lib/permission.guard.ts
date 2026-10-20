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
 *
 * `excludeRoles` handles a real mismatch: some roles hold a `:read`
 * permission for a narrow, single-record API need (e.g. `driver` holds
 * `customers:read` only to resolve the delivery address on their own
 * order — see the role grants' own code comments in
 * `fa52b77ec442_create_identity_schema_and_rbac_tables.py` and friends) but
 * that same coarse permission code also happens to gate the full
 * staff-facing "browse everything" list page for that resource. Pass the
 * roles that should be denied this *page* despite holding the permission.
 *
 * A denied tenant user is sent to `/no-access` (an explicit "you don't have
 * access" page), not silently back to Home.
 */
export function permissionGuard(
  permissionCode: string,
  excludeRoles?: readonly string[],
): CanActivateFn {
  return () => {
    const authService = inject(AuthService);
    const tokenStore = inject(AuthTokenStore);
    const router = inject(Router);

    return authService.ensureSessionRestored().pipe(
      map(() => {
        const principal = tokenStore.principal();
        const allowed =
          !!principal?.permissions.has(permissionCode) && !excludeRoles?.includes(principal.role);
        if (allowed) {
          return true;
        }
        // A tenant user gets the shell's explicit "no access" page (DO-31);
        // a platform session has no tenant shell, so it goes back to the
        // Platform Console instead.
        return router.createUrlTree([
          principal?.role === 'super_admin' ? '/platform' : '/no-access',
        ]);
      }),
    );
  };
}
