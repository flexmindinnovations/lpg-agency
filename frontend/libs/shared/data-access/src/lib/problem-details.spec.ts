import { HttpErrorResponse } from '@angular/common/http';
import { toAppError, type ProblemDetails } from './problem-details';

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
