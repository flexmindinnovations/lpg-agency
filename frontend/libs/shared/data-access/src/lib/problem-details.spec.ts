import { HttpErrorResponse } from '@angular/common/http';
import { errorMessageFor, isAppError, toAppError, type AppError, type ProblemDetails } from './problem-details';

describe('toAppError', () => {
  it('maps an RFC 7807 body to a typed error', () => {
    const problem: ProblemDetails = {
      type: 'https://api.lpgplatform.com/errors/resource-not-found',
      title: 'Resource not found',
      status: 404,
      error_code: 'RESOURCE_NOT_FOUND',
      detail: 'No customer exists with the supplied identifier.',
      instance: '/api/v1/customers/abc',
      trace_id: 'trace-123',
    };

    const result = toAppError(new HttpErrorResponse({ status: 404, error: problem }));

    expect(result).toEqual({
      status: 404,
      errorCode: 'RESOURCE_NOT_FOUND',
      title: 'Resource not found',
      detail: 'No customer exists with the supplied identifier.',
      traceId: 'trace-123',
      fieldErrors: undefined,
      isNetworkError: false,
    });
  });

  it('carries field errors through for form display', () => {
    const problem: ProblemDetails = {
      type: 'x',
      title: 'Request validation failed',
      status: 422,
      error_code: 'REQUEST_VALIDATION_FAILED',
      detail: 'Invalid.',
      errors: { quantity: ['must be greater than zero'] },
    };

    const result = toAppError(new HttpErrorResponse({ status: 422, error: problem }));

    expect(result.fieldErrors).toEqual({ quantity: ['must be greater than zero'] });
  });

  it('distinguishes a network failure from a server error', () => {
    // status 0 means the request never reached the server. Showing "server
    // error" there sends the user chasing the wrong problem.
    const result = toAppError(new HttpErrorResponse({ status: 0 }));

    expect(result.isNetworkError).toBe(true);
    expect(result.errorCode).toBe('NETWORK_UNAVAILABLE');
  });

  it('handles a non-Problem-Details body without throwing', () => {
    // A proxy or gateway can answer before the application does.
    const result = toAppError(
      new HttpErrorResponse({ status: 502, error: '<html>Bad Gateway</html>' }),
    );

    expect(result.errorCode).toBe('UNEXPECTED_RESPONSE');
    expect(result.isNetworkError).toBe(false);
  });
});

describe('isAppError', () => {
  it('recognises a value shaped like AppError', () => {
    expect(isAppError({ errorCode: 'X' })).toBe(true);
  });

  it('rejects anything else', () => {
    expect(isAppError(null)).toBe(false);
    expect(isAppError(undefined)).toBe(false);
    expect(isAppError('oops')).toBe(false);
    expect(isAppError({ message: 'no error code here' })).toBe(false);
  });
});

describe('errorMessageFor', () => {
  const appError = (over: Partial<AppError> = {}): AppError => ({
    status: 400,
    errorCode: 'SOME_CODE',
    title: 'Title',
    detail: '',
    isNetworkError: false,
    ...over,
  });

  it('falls back for a non-AppError value', () => {
    expect(errorMessageFor('boom')).toBe('Something went wrong. Please try again.');
    expect(errorMessageFor('boom', 'Custom fallback.')).toBe('Custom fallback.');
  });

  it('reports a network failure distinctly', () => {
    expect(errorMessageFor(appError({ isNetworkError: true }))).toBe(
      'Cannot reach the server. Check your connection and try again.',
    );
  });

  it.each([
    ['PERMISSION_DENIED', "You don't have permission to do that."],
    ['INVALID_STATE_TRANSITION', 'That action is not valid for the order in its current state.'],
    ['INSUFFICIENT_VEHICLE_STOCK', 'Not enough stock reserved on the vehicle for that quantity.'],
    ['INCOMPLETE_PROOF_OF_DELIVERY', 'Proof of delivery is incomplete or invalid.'],
    ['OTP_MISMATCH', 'The OTP entered is incorrect.'],
    ['OTP_EXPIRED', 'The OTP has expired — depart again to issue a new one.'],
    ['IDEMPOTENCY_KEY_CONFLICT', 'This request was already submitted with different details.'],
    [
      'LICENSE_ACTIVATION_FAILED',
      'That key is invalid, already activated, or has been revoked.',
    ],
    [
      'DUPLICATE_CYLINDER_SERIAL_NUMBER',
      'A cylinder unit with this serial number is already registered.',
    ],
    [
      'DUPLICATE_CYLINDER_QR_CODE',
      'A cylinder unit with this QR / barcode is already registered.',
    ],
    ['DUPLICATE_REGISTRATION_NUMBER', 'A vehicle with this registration number already exists.'],
    ['DUPLICATE_EMPLOYEE_CODE', 'A driver with this employee code already exists.'],
    ['DUPLICATE_PHONE', 'A customer with this phone number already exists.'],
    ['DUPLICATE_CONSUMER_NUMBER', 'This Consumer Number is already assigned.'],
    ['DUPLICATE_LPG_SUBSIDY_ID', 'This LPG ID is already linked to another customer.'],
  ])('maps %s to a friendly message', (code, expected) => {
    expect(errorMessageFor(appError({ errorCode: code }))).toBe(expected);
  });

  it('prefers the backend detail for RESOURCE_NOT_FOUND when present', () => {
    expect(
      errorMessageFor(appError({ errorCode: 'RESOURCE_NOT_FOUND', detail: 'No such branch.' })),
    ).toBe('No such branch.');
  });

  it('falls back to a generic message for RESOURCE_NOT_FOUND with no detail', () => {
    expect(errorMessageFor(appError({ errorCode: 'RESOURCE_NOT_FOUND', detail: '' }))).toBe(
      'That resource could not be found.',
    );
  });

  it('uses the backend detail for an unmapped code', () => {
    expect(
      errorMessageFor(appError({ errorCode: 'SOME_UNMAPPED_CODE', detail: 'A specific reason.' })),
    ).toBe('A specific reason.');
  });

  it('uses the fallback for an unmapped code with no detail', () => {
    expect(errorMessageFor(appError({ errorCode: 'SOME_UNMAPPED_CODE', detail: '' }))).toBe(
      'Something went wrong. Please try again.',
    );
    expect(
      errorMessageFor(appError({ errorCode: 'SOME_UNMAPPED_CODE', detail: '' }), 'Custom.'),
    ).toBe('Custom.');
  });
});
