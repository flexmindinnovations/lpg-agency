import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { InjectionToken, inject } from '@angular/core';
import { ConfirmationService } from 'primeng/api';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthTokenStore } from './auth-token.store';
import { HARD_NAVIGATE } from './hard-navigate';

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
 * (or a 401 from an auth endpoint) clears the session, surfaces a
 * "Session Expired" confirm dialog, and re-throws the error rather than
 * swallowing it — every caller still gets a normal error notification
 * (`problemDetailsInterceptor` downstream, and any guard/component's own
 * `catchError`). Returning `EMPTY` here previously meant those observables
 * completed with zero emissions instead of erroring, which is exactly what
 * RxJS/Angular Router's guard-combination logic throws `EmptyError: no
 * elements in sequence` for — the practical case being a `super_admin`
 * session hitting a tenant-scoped endpoint like `/admin/license/status`:
 * refresh always succeeds (the token itself is valid) but the retry always
 * 401s again too (wrong session type, not an expiry), so this path fires on
 * every request, not just genuine expiry. Order in `app.config.ts`:
 * `[correlationIdInterceptor, authInterceptor, problemDetailsInterceptor]`.
 */
// Several requests fail together when a session ends; one dialog is enough. Held in an
// injectable (not a module variable) so each app instance and each test starts clean.
const SESSION_EXPIRED_DIALOG = new InjectionToken<{ open: boolean }>('SESSION_EXPIRED_DIALOG', {
  providedIn: 'root',
  factory: () => ({ open: false }),
});

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const authService = inject(AuthService);
  const tokenStore = inject(AuthTokenStore);
  const hardNavigate = inject(HARD_NAVIGATE);
  const dialogState = inject(SESSION_EXPIRED_DIALOG);
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
          catchError((retryError: unknown) => {
            tokenStore.clear();
            if (!dialogState.open) {
              dialogState.open = true;
              // A full page load, not `router.navigate`: see `HARD_NAVIGATE`. The dialog
              // cannot be dismissed any other way, so the user always ends up at sign-in.
              const toLogin = () => hardNavigate('/login');
              confirmationService.confirm({
                header: 'Session Expired',
                message: 'Your session has expired. Please log in again to continue.',
                icon: 'pi pi-exclamation-circle',
                acceptLabel: 'Log In',
                rejectVisible: false,
                closable: false,
                closeOnEscape: false,
                accept: toLogin,
                reject: toLogin,
              });
            }
            return throwError(() => retryError);
          }),
        );
      }
      return throwError(() => error);
    }),
  );
};
