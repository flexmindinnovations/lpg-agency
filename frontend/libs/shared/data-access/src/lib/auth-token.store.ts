import { Injectable, signal } from '@angular/core';

/** The decoded shape of `GET /auth/me`, kept alongside the access token. */
export interface AuthPrincipal {
  readonly userId: string;
  readonly tenantId: string | null;
  readonly role: string;
  readonly permissions: ReadonlySet<string>;
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
