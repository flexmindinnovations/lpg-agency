import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { errorMessageFor, isAppError } from './problem-details';
import { NotifyService } from './services/notify.service';

/** Never bearer-attach or retry-on-401 the endpoints that issue/rotate
 * tokens themselves (matches auth.interceptor.ts's own list) — those
 * screens render their errors inline (`<p-message>`), not via toast;
 * auto-toasting too would double the message. */
const AUTH_ENDPOINT_SEGMENTS = ['/auth/login', '/auth/refresh', '/auth/otp/verify'];

/** Only mutating requests auto-toast. A failed GET is usually a data-grid
 * or panel load that already has its own empty/error state — toasting
 * every one of those would be a much bigger behavior change than the
 * "data modification, new record" gap this was built to close. A GET
 * that genuinely needs error feedback (e.g. the notification drawer's
 * user-initiated load) calls NotifyService directly instead. */
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function isAuthEndpoint(url: string): boolean {
  return AUTH_ENDPOINT_SEGMENTS.some((segment) => url.includes(segment));
}

/**
 * The single, app-wide place that auto-toasts a failed mutation.
 *
 * Replaces the ~18 hand-rolled `messageService.add({severity:'error',...})`
 * call sites this codebase had accumulated, and closes 3 features that had
 * none at all (order-detail, feature-dispatch, feature-inventory).
 *
 * Registration order in app.config.ts matters: this must sit *before*
 * `problemDetailsInterceptor` in the array so its response-side
 * `catchError` runs *after* problemDetailsInterceptor's conversion (array
 * order is reversed on the response path — see the comment there) — it
 * needs the typed `AppError`, not the raw `HttpErrorResponse`. It must
 * also run after `authInterceptor`'s own 401-refresh-retry/session-dialog
 * handling has had its chance, which the same ordering gives it.
 */
export const globalErrorToastInterceptor: HttpInterceptorFn = (request, next) => {
  const notify = inject(NotifyService);

  return next(request).pipe(
    catchError((error: unknown) => {
      // Checked against both shapes: in production this always runs after
      // problemDetailsInterceptor has converted the error to an AppError,
      // but a defensive check against the raw HttpErrorResponse too means
      // this stays correct even if that ordering ever changes, or this
      // interceptor is reused in a config that composes it differently.
      const status = isAppError(error)
        ? error.status
        : error instanceof HttpErrorResponse
          ? error.status
          : null;
      const isAuthOrSessionExpiry = isAuthEndpoint(request.url) || status === 401;

      if (MUTATING_METHODS.has(request.method) && !isAuthOrSessionExpiry) {
        notify.error(errorMessageFor(error));
      }

      return throwError(() => error);
    }),
  );
};
