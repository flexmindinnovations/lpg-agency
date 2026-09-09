import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ConfirmationService, MessageService } from 'primeng/api';
import { authInterceptor } from './auth.interceptor';
import { globalErrorToastInterceptor } from './global-error-toast.interceptor';
import { problemDetailsInterceptor, type ProblemDetails } from './problem-details';
import { AuthTokenStore } from './auth-token.store';
import { NotifyService } from './services/notify.service';

const problem = (over: Partial<ProblemDetails> = {}): ProblemDetails => ({
  type: 'x',
  title: 'Bad request',
  status: 400,
  error_code: 'SOME_CODE',
  detail: 'A specific reason from the backend.',
  ...over,
});

describe('globalErrorToastInterceptor', () => {
  let http: HttpClient;
  let httpTesting: HttpTestingController;
  let notifyService: NotifyService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([globalErrorToastInterceptor])),
        provideHttpClientTesting(),
        MessageService,
      ],
    });

    http = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
    notifyService = TestBed.inject(NotifyService);
  });

  afterEach(() => httpTesting.verify());

  it('toasts a failed mutating request', () => {
    const errorSpy = jest.spyOn(notifyService, 'error');

    http.post('/api/v1/admin/branches', {}).subscribe({ error: () => undefined });
    httpTesting.expectOne('/api/v1/admin/branches').flush(problem(), { status: 400, statusText: 'Bad Request' });

    expect(errorSpy).toHaveBeenCalledTimes(1);
  });

  it('does not toast a failed GET', () => {
    const errorSpy = jest.spyOn(notifyService, 'error');

    http.get('/api/v1/orders').subscribe({ error: () => undefined });
    httpTesting.expectOne('/api/v1/orders').flush(problem(), { status: 400, statusText: 'Bad Request' });

    expect(errorSpy).not.toHaveBeenCalled();
  });

  it('does not toast a failed request to an auth endpoint', () => {
    const errorSpy = jest.spyOn(notifyService, 'error');

    http.post('/api/v1/auth/login', {}).subscribe({ error: () => undefined });
    httpTesting
      .expectOne('/api/v1/auth/login')
      .flush(problem({ error_code: 'INVALID_CREDENTIALS' }), { status: 401, statusText: 'Unauthorized' });

    expect(errorSpy).not.toHaveBeenCalled();
  });

  it('does not toast a 401 on an ordinary endpoint (the session-expired dialog owns that)', () => {
    const errorSpy = jest.spyOn(notifyService, 'error');

    http.patch('/api/v1/admin/branches/b1/rename', {}).subscribe({ error: () => undefined });
    httpTesting
      .expectOne('/api/v1/admin/branches/b1/rename')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(errorSpy).not.toHaveBeenCalled();
  });

  it('still rethrows the error to the caller after toasting', () => {
    let observedError: unknown;

    http.post('/api/v1/admin/branches', {}).subscribe({ error: (error) => (observedError = error) });
    httpTesting.expectOne('/api/v1/admin/branches').flush(problem(), { status: 400, statusText: 'Bad Request' });

    expect(observedError).toBeTruthy();
  });
});

describe('globalErrorToastInterceptor composed in production order', () => {
  // Order here must match app.config.ts's withInterceptors([...]) array:
  // [correlationId, globalErrorToast, problemDetails, auth]. This proves
  // the interceptor sees the *converted* AppError (with its friendly
  // errorMessageFor text), not a raw HttpErrorResponse, and that it stays
  // silent on the 401 authInterceptor already puts a dialog in front of.
  let http: HttpClient;
  let httpTesting: HttpTestingController;
  let notifyService: NotifyService;
  let tokenStore: AuthTokenStore;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(
          withInterceptors([globalErrorToastInterceptor, problemDetailsInterceptor, authInterceptor]),
        ),
        provideHttpClientTesting(),
        provideRouter([]),
        ConfirmationService,
        MessageService,
      ],
    });

    http = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
    notifyService = TestBed.inject(NotifyService);
    tokenStore = TestBed.inject(AuthTokenStore);
  });

  afterEach(() => httpTesting.verify());

  it('toasts the converted, friendly message for a failed mutation', () => {
    const errorSpy = jest.spyOn(notifyService, 'error');

    http.post('/api/v1/admin/branches', {}).subscribe({ error: () => undefined });
    httpTesting
      .expectOne('/api/v1/admin/branches')
      .flush(problem({ error_code: 'PERMISSION_DENIED' }), { status: 403, statusText: 'Forbidden' });

    expect(errorSpy).toHaveBeenCalledWith("You don't have permission to do that.");
  });

  it('stays silent on a 401 that authInterceptor turns into a session-expired dialog', () => {
    tokenStore.setAccessToken('stale-token');
    const errorSpy = jest.spyOn(notifyService, 'error');

    http.patch('/api/v1/admin/branches/b1/rename', {}).subscribe({ error: () => undefined });
    httpTesting
      .expectOne('/api/v1/admin/branches/b1/rename')
      .flush(null, { status: 401, statusText: 'Unauthorized' });
    httpTesting.expectOne('/api/v1/auth/refresh').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(errorSpy).not.toHaveBeenCalled();
  });
});
