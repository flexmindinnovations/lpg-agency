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

/**
 * True when `value` is a normalised `AppError` — the type every HTTP
 * failure becomes via `toAppError`/`problemDetailsInterceptor`.
 *
 * The one canonical version of a check 27+ feature files used to
 * hand-duplicate. Anything that still needs its own copy is wrong, not
 * this one.
 */
export function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

/**
 * A human-readable message for any caught error, for direct display
 * (a toast, an inline banner).
 *
 * Covers the error codes that recur across features (permission, not
 * found, OTP, idempotency, ...) plus the couple of codes worth a
 * dedicated message app-wide. Anything unmapped falls back to the
 * backend's own RFC 7807 `detail` text (already written for a human)
 * rather than a flat generic string, so this stays useful even for
 * domain errors it doesn't know about by name.
 */
export function errorMessageFor(
  error: unknown,
  fallback = 'Something went wrong. Please try again.',
): string {
  if (!isAppError(error)) {
    return fallback;
  }
  if (error.isNetworkError) {
    return 'Cannot reach the server. Check your connection and try again.';
  }
  switch (error.errorCode) {
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    case 'RESOURCE_NOT_FOUND':
      // The backend's own detail already names the specific resource.
      return error.detail || 'That resource could not be found.';
    case 'INVALID_STATE_TRANSITION':
      return 'That action is not valid for the order in its current state.';
    case 'INSUFFICIENT_VEHICLE_STOCK':
      return 'Not enough stock reserved on the vehicle for that quantity.';
    case 'INCOMPLETE_PROOF_OF_DELIVERY':
      return 'Proof of delivery is incomplete or invalid.';
    case 'OTP_MISMATCH':
      return 'The OTP entered is incorrect.';
    case 'OTP_EXPIRED':
      return 'The OTP has expired — depart again to issue a new one.';
    case 'IDEMPOTENCY_KEY_CONFLICT':
      return 'This request was already submitted with different details.';
    case 'LICENSE_ACTIVATION_FAILED':
      return 'That key is invalid, already activated, or has been revoked.';
    case 'DUPLICATE_CYLINDER_SERIAL_NUMBER':
      return 'A cylinder unit with this serial number is already registered.';
    case 'DUPLICATE_CYLINDER_QR_CODE':
      return 'A cylinder unit with this QR / barcode is already registered.';
    case 'DUPLICATE_REGISTRATION_NUMBER':
      return 'A vehicle with this registration number already exists.';
    case 'DUPLICATE_EMPLOYEE_CODE':
      return 'A driver with this employee code already exists.';
    case 'DUPLICATE_PHONE':
      return 'A customer with this phone number already exists.';
    case 'DUPLICATE_CONSUMER_NUMBER':
      return 'This Consumer Number is already assigned.';
    case 'DUPLICATE_LPG_SUBSIDY_ID':
      return 'This LPG ID is already linked to another customer.';
    default:
      return error.detail || fallback;
  }
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
