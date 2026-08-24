import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { catchError, map, of, switchMap } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthTokenStore } from './auth-token.store';
import { LicenseService } from './license.service';
import { LicenseStatusStore, type LicenseLifecycleState } from './license-status.store';

const _BLOCKING_STATES: readonly LicenseLifecycleState[] = [
  'pending_activation',
  'blocked',
  'revoked',
];

/** `/admin/license*` must stay reachable even while blocked — it's the one
 * place a tenant can actually fix a blocked state (activate/renew). Without
 * this exemption, clicking through from `/license-required` to
 * `/admin/license` would immediately bounce right back here. */
function isLicenseManagementRoute(url: string): boolean {
  return url.startsWith('/admin/license');
}

/**
 * Hard gate — blocks navigation into the shell when this tenant's license
 * is not yet activated, expired past grace, or revoked. Redirects to
 * `/license-required`, a shell-sibling route (same reasoning `/login` is
 * one) so it renders with no nav chrome.
 *
 * Makes its own live call rather than trusting `LicenseStatusStore`'s
 * already-cached value — `AuthService.hydrateSession()` populates that
 * store fire-and-forget, so it may not have resolved yet by the time this
 * guard runs immediately after `authGuard`. A fetch failure here fails
 * *open* (allows navigation) — this is a UX convenience only; the actual
 * enforcement boundary is server-side (`JwtTenantResolver`'s per-request
 * check), so a bypassed or failed client check can never itself grant
 * access to data.
 *
 * Calls `AuthService.ensureSessionRestored()` itself first rather than
 * trusting `authGuard` to have already resolved one on this same
 * navigation — see that method's own docstring: without this, a hard
 * reload could fire this guard's `getStatus()` call before the access
 * token is set, 401ing every time regardless of the actual license state.
 * Cheap no-op once a session already exists.
 *
 * Also the tenant shell's own defense against a `super_admin` session
 * landing here at all — e.g. a stale bookmark to `/`, or `permissionGuard`
 * denying some other tenant-scoped route and falling back to `/`
 * (`permission.guard.ts`'s own redirect target). `getStatus()` is
 * tenant-scoped and always 401s for a `tenant_id = null` session
 * regardless of the real license state, so redirect to `/platform` before
 * ever making that call, rather than showing a misleading "Session
 * Expired" dialog for a session that hasn't actually expired.
 */
export const licenseGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const tokenStore = inject(AuthTokenStore);
  const licenseService = inject(LicenseService);
  const licenseStatusStore = inject(LicenseStatusStore);
  const router = inject(Router);

  return authService.ensureSessionRestored().pipe(
    switchMap(() => {
      if (tokenStore.principal()?.role === 'super_admin') {
        return of(router.createUrlTree(['/platform']));
      }

      return licenseService.getStatus().pipe(
        map((response) => {
          licenseStatusStore.set({
            status: response.status as LicenseLifecycleState,
            planTier: response.plan_tier,
            keyPrefix: response.key_prefix,
            activatedAt: response.activated_at,
            expiresAt: response.expires_at,
            graceEndsAt: response.grace_ends_at,
          });
          if (
            _BLOCKING_STATES.includes(response.status as LicenseLifecycleState) &&
            !isLicenseManagementRoute(state.url)
          ) {
            return router.createUrlTree(['/license-required']);
          }
          return true;
        }),
      );
    }),
    catchError(() => of(true)),
  );
};
