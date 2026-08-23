import { Injectable, signal } from '@angular/core';

export type LicenseLifecycleState =
  | 'pending_activation'
  | 'active'
  | 'grace'
  | 'blocked'
  | 'revoked';

export interface LicenseStatus {
  readonly status: LicenseLifecycleState;
  readonly planTier: string | null;
  readonly keyPrefix: string | null;
  readonly activatedAt: string | null;
  readonly expiresAt: string | null;
  readonly graceEndsAt: string | null;
}

/**
 * In-memory holder for the current tenant's license status — mirrors
 * `AuthTokenStore`'s shape. Populated once per session inside
 * `AuthService.hydrateSession()`, fire-and-forget: a transient fetch
 * failure here must never itself lock a user out of an otherwise-valid
 * session, since the actual enforcement boundary is server-side
 * (`JwtTenantResolver`'s per-request check), not this client-side cache.
 */
@Injectable({ providedIn: 'root' })
export class LicenseStatusStore {
  private readonly statusSignal = signal<LicenseStatus | null>(null);

  readonly status = this.statusSignal.asReadonly();

  set(status: LicenseStatus): void {
    this.statusSignal.set(status);
  }

  clear(): void {
    this.statusSignal.set(null);
  }
}
