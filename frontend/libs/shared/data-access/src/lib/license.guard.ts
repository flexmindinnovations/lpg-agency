import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { catchError, map, of } from 'rxjs';
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
 * `authGuard` must run first on any route using this — it assumes a
 * resolved principal already exists.
 */
export const licenseGuard: CanActivateFn = (_route, state) => {
  const licenseService = inject(LicenseService);
  const licenseStatusStore = inject(LicenseStatusStore);
  const router = inject(Router);

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
    catchError(() => of(true)),
  );
};
