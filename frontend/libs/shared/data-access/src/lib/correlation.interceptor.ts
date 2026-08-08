import { HttpInterceptorFn } from '@angular/common/http';

export const CORRELATION_ID_HEADER = 'X-Correlation-ID';

/**
 * Attaches a correlation ID to every outbound request.
 *
 * The backend accepts this header, binds it to its logging context, and echoes
 * it back (`12-observability.md` §4). Sending one from the client means a
 * user-reported problem can be traced through the API, into domain event
 * dispatch, into any background job it triggered — without asking the user to
 * reproduce it.
 */
export const correlationIdInterceptor: HttpInterceptorFn = (request, next) =>
  next(
    request.clone({
      setHeaders: { [CORRELATION_ID_HEADER]: crypto.randomUUID() },
    }),
  );
