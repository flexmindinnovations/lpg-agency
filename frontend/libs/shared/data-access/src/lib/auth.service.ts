import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, finalize, map, of, shareReplay, switchMap, tap } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { loginApiV1AuthLoginPost } from './generated/fn/authentication/login-api-v-1-auth-login-post';
import { logoutApiV1AuthLogoutPost } from './generated/fn/authentication/logout-api-v-1-auth-logout-post';
import { meApiV1AuthMeGet } from './generated/fn/authentication/me-api-v-1-auth-me-get';
import { otpRequestApiV1AuthOtpRequestPost } from './generated/fn/authentication/otp-request-api-v-1-auth-otp-request-post';
import { otpVerifyApiV1AuthOtpVerifyPost } from './generated/fn/authentication/otp-verify-api-v-1-auth-otp-verify-post';
import { passwordForgotApiV1AuthPasswordForgotPost } from './generated/fn/authentication/password-forgot-api-v-1-auth-password-forgot-post';
import { passwordResetApiV1AuthPasswordResetPost } from './generated/fn/authentication/password-reset-api-v-1-auth-password-reset-post';
import { refreshApiV1AuthRefreshPost } from './generated/fn/authentication/refresh-api-v-1-auth-refresh-post';
import type { PrincipalResponse } from './generated/models/principal-response';
import { AuthPrincipal, AuthTokenStore } from './auth-token.store';

function toAuthPrincipal(response: PrincipalResponse): AuthPrincipal {
  return {
    userId: response.user_id,
    tenantId: response.tenant_id,
    role: response.role,
    permissions: new Set(response.permissions),
  };
}

/**
 * Thin wrapper over the generated `/auth/*` client functions.
 *
 * The refresh token itself never appears here — the Dashboard is a browser
 * client, so the backend's `HttpOnly`/`Secure`/`SameSite=Strict` cookie
 * carries it (`api/v1/routers/auth.py`'s module docstring); every call below
 * omits `refresh_token` from the request body and relies on the cookie
 * instead, with `authInterceptor` attaching `withCredentials: true`.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);
  private readonly tokenStore = inject(AuthTokenStore);

  readonly accessToken = this.tokenStore.accessToken;
  readonly principal = this.tokenStore.principal;

  private refreshInFlight$: Observable<string> | null = null;

  login(email: string, password: string): Observable<void> {
    return loginApiV1AuthLoginPost(this.http, this.config.rootUrl, {
      body: { email, password },
    }).pipe(
      map((response) => response.body.access_token),
      switchMap((accessToken) => this.hydrateSession(accessToken)),
    );
  }

  requestOtp(tenantId: string, phoneNumber: string): Observable<void> {
    return otpRequestApiV1AuthOtpRequestPost(this.http, this.config.rootUrl, {
      body: { tenant_id: tenantId, phone_number: phoneNumber },
    }).pipe(map(() => undefined));
  }

  verifyOtp(tenantId: string, phoneNumber: string, code: string): Observable<void> {
    return otpVerifyApiV1AuthOtpVerifyPost(this.http, this.config.rootUrl, {
      body: { tenant_id: tenantId, phone_number: phoneNumber, code },
    }).pipe(
      map((response) => response.body.access_token),
      switchMap((accessToken) => this.hydrateSession(accessToken)),
    );
  }

  requestPasswordReset(email: string): Observable<void> {
    return passwordForgotApiV1AuthPasswordForgotPost(this.http, this.config.rootUrl, {
      body: { email },
    }).pipe(map(() => undefined));
  }

  confirmPasswordReset(resetToken: string, newPassword: string): Observable<void> {
    return passwordResetApiV1AuthPasswordResetPost(this.http, this.config.rootUrl, {
      body: { reset_token: resetToken, new_password: newPassword },
    }).pipe(map(() => undefined));
  }

  /**
   * Redeems the `HttpOnly` refresh cookie for a new access token.
   *
   * Concurrent callers (e.g. several requests failing with 401 at once)
   * share a single in-flight refresh via `shareReplay(1)` rather than each
   * triggering their own rotation — a second, unrelated redemption of the
   * same refresh token would otherwise trip reuse detection
   * (`17-api-security.md` §2) and revoke the whole session.
   */
  refreshAccessToken(): Observable<string> {
    if (!this.refreshInFlight$) {
      this.refreshInFlight$ = refreshApiV1AuthRefreshPost(this.http, this.config.rootUrl, {
        body: {},
      }).pipe(
        map((response) => response.body.access_token),
        tap((accessToken) => this.tokenStore.setAccessToken(accessToken)),
        shareReplay(1),
        finalize(() => {
          this.refreshInFlight$ = null;
        }),
      );
    }
    return this.refreshInFlight$;
  }

  /**
   * Silently re-establishes a session from the refresh cookie alone —
   * called once at app startup, since the in-memory access token does not
   * survive a page reload by design.
   */
  restoreSession(): Observable<boolean> {
    return this.refreshAccessToken().pipe(
      switchMap((accessToken) => this.hydrateSession(accessToken)),
      map(() => true),
      catchError(() => {
        this.tokenStore.clear();
        return of(false);
      }),
    );
  }

  logout(): Observable<void> {
    return logoutApiV1AuthLogoutPost(this.http, this.config.rootUrl, { body: {} }).pipe(
      map(() => undefined),
      // Logout is idempotent server-side too (`logout.py`'s module
      // docstring) — clear the local session regardless of whether the
      // request itself succeeded.
      catchError(() => of(undefined)),
      tap(() => this.tokenStore.clear()),
    );
  }

  private hydrateSession(accessToken: string): Observable<void> {
    this.tokenStore.setAccessToken(accessToken);
    return meApiV1AuthMeGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
      tap((principal) => this.tokenStore.setSession(accessToken, toAuthPrincipal(principal))),
      map(() => undefined),
    );
  }
}
