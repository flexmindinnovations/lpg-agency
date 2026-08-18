import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { ConfirmationService } from 'primeng/api';
import { catchError, switchMap, throwError, EMPTY } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthTokenStore } from './auth-token.store';

/** Never bearer-attach or retry-on-401 the endpoints that issue/rotate tokens themselves. */
const AUTH_ENDPOINT_SEGMENTS = ['/auth/login', '/auth/refresh', '/auth/otp/verify'];

function isAuthEndpoint(url: string): boolean {
  return AUTH_ENDPOINT_SEGMENTS.some((segment) => url.includes(segment));
}

/**
 * Attaches the bearer access token to every request and always sends
 * credentials (cookies) — the refresh-token cookie is `HttpOnly`, so this is
 * the only way `/auth/refresh` ever sees it.
 *
 * On a 401 from anything other than the token-issuing endpoints themselves,
 * attempts one silent refresh-and-retry before giving up; a second failure
 * (or a 401 from an auth endpoint) clears the session and lets the error
 * flow through to `problemDetailsInterceptor` unchanged, so route guards can
 * react to it. Order in `app.config.ts`:
 * `[correlationIdInterceptor, authInterceptor, problemDetailsInterceptor]`.
 */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const authService = inject(AuthService);
  const tokenStore = inject(AuthTokenStore);
  const router = inject(Router);
  const confirmationService = inject(ConfirmationService);

  const token = tokenStore.accessToken();
  const withAuth = request.clone({
    ...(token ? { setHeaders: { Authorization: `Bearer ${token}` } } : {}),
    withCredentials: true,
  });

  return next(withAuth).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        !isAuthEndpoint(request.url)
      ) {
        return authService.refreshAccessToken().pipe(
          switchMap((newAccessToken) =>
            next(withAuth.clone({ setHeaders: { Authorization: `Bearer ${newAccessToken}` } })),
          ),
          catchError(() => {
            tokenStore.clear();
            confirmationService.confirm({
              header: 'Session Expired',
              message: 'Your session has expired. Please log in again to continue.',
              icon: 'pi pi-exclamation-circle',
              acceptLabel: 'Log In',
              rejectVisible: false,
              accept: () => {
                void router.navigate(['/login']);
              }
            });
            return EMPTY; // Suppress further error handling so problemDetails doesn't show a generic toast
          }),
        );
      }
      return throwError(() => error);
    }),
  );
};
