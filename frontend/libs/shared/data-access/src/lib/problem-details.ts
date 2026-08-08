import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

/**
 * RFC 7807 Problem Details, as the backend emits them (ADR-021).
 *
 * `snake_case` because that is the wire format for the whole API
 * (`docs/data/10-api-design-guidelines.md`) — no case translation anywhere in
 * the stack.
 */
export interface ProblemDetails {
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly error_code: string;
  readonly detail: string;
  readonly instance?: string;
  readonly trace_id?: string;
  /** Field-level validation failures, keyed by field path. */
  readonly errors?: Readonly<Record<string, readonly string[]>>;
}

/** A normalised application error. Every HTTP failure becomes one of these. */
export interface AppError {
  readonly status: number;
  readonly errorCode: string;
  readonly title: string;
  readonly detail: string;
  readonly traceId?: string;
  readonly fieldErrors?: Readonly<Record<string, readonly string[]>>;
  /** True when the server did not answer at all — offline, DNS, CORS, timeout. */
  readonly isNetworkError: boolean;
}

const isProblemDetails = (value: unknown): value is ProblemDetails =>
  typeof value === 'object' &&
  value !== null &&
  'error_code' in value &&
  'title' in value &&
  'status' in value;

/**
 * Convert any `HttpErrorResponse` into an `AppError`.
 *
 * Exported separately from the interceptor so it can be unit-tested directly
 * and reused wherever an error is handled outside the HTTP pipeline.
 */
export function toAppError(response: HttpErrorResponse): AppError {
  // status 0 means the request never reached the server.
  if (response.status === 0) {
    return {
      status: 0,
      errorCode: 'NETWORK_UNAVAILABLE',
      title: 'Cannot reach the server',
      detail: 'Check your connection and try again.',
      isNetworkError: true,
    };
  }

  if (isProblemDetails(response.error)) {
    const problem = response.error;
    return {
      status: problem.status,
      errorCode: problem.error_code,
      title: problem.title,
      detail: problem.detail,
      traceId: problem.trace_id,
      fieldErrors: problem.errors,
      isNetworkError: false,
    };
  }

  // A non-Problem-Details error body means something upstream of the
  // application answered — a proxy, a gateway, a misconfigured route. Worth
  // surfacing distinctly rather than pretending it was a normal API error.
  return {
    status: response.status,
    errorCode: 'UNEXPECTED_RESPONSE',
    title: 'Unexpected server response',
    detail: response.message || 'The server returned an unrecognised error.',
    isNetworkError: false,
  };
}

/**
 * Translates every HTTP failure into a typed `AppError`.
 *
 * One interceptor rather than per-screen parsing: components should never
 * inspect an error body, and a single translation point is what makes the
 * one-error-contract decision (ADR-021) actually pay off.
 */
export const problemDetailsInterceptor: HttpInterceptorFn = (request, next) =>
  next(request).pipe(
    catchError((response: unknown) =>
      throwError(() => (response instanceof HttpErrorResponse ? toAppError(response) : response)),
    ),
  );
