import { Injectable, signal } from '@angular/core';

/** The decoded shape of `GET /auth/me`, kept alongside the access token. */
export interface AuthPrincipal {
  readonly userId: string;
  readonly tenantId: string | null;
  readonly role: string;
  readonly permissions: Set<string>;
  readonly email: string | null;
  /** Home branch of a branch-bound staff member; null/absent for tenant-wide
   * roles. A UI default only — the API enforces branch scope itself. */
  readonly branchId?: string | null;
}

/**
 * In-memory-only holder for the access token and the signed-in principal.
 *
 * Deliberately never persisted to `localStorage`/`sessionStorage` — an XSS
 * payload that can read storage should not walk away with a bearer token
 * (`08-security-architecture.md` §2). The refresh token never reaches this
 * store at all: it lives only in the `HttpOnly` cookie the backend sets, so
 * a page reload re-authenticates via `AuthService.restoreSession()` rather
 * than by reading anything client-script-accessible.
 */
@Injectable({ providedIn: 'root' })
export class AuthTokenStore {
  private readonly accessTokenSignal = signal<string | null>(null);
  private readonly principalSignal = signal<AuthPrincipal | null>(null);

  readonly accessToken = this.accessTokenSignal.asReadonly();
  readonly principal = this.principalSignal.asReadonly();

  /** The branch a form should pre-select: the staff member's home branch
   * when it is among `branches`, otherwise the only branch there is, otherwise
   * none (the user picks). */
  defaultBranchIdAmong(branches: readonly { readonly id: string }[]): string | null {
    const home = this.principalSignal()?.branchId;
    if (home && branches.some((b) => b.id === home)) return home;
    return branches.length === 1 ? branches[0].id : null;
  }

  setSession(accessToken: string, principal: AuthPrincipal): void {
    this.accessTokenSignal.set(accessToken);
    this.principalSignal.set(principal);
  }

  setAccessToken(accessToken: string): void {
    this.accessTokenSignal.set(accessToken);
  }

  clear(): void {
    this.accessTokenSignal.set(null);
    this.principalSignal.set(null);
  }
}
