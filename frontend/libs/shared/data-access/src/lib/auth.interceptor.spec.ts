import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ConfirmationService } from 'primeng/api';
import { authInterceptor } from './auth.interceptor';
import { AuthTokenStore } from './auth-token.store';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpTesting: HttpTestingController;
  let tokenStore: AuthTokenStore;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
        ConfirmationService,
      ],
    });

    http = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
    tokenStore = TestBed.inject(AuthTokenStore);
  });

  afterEach(() => httpTesting.verify());

  it('attaches the bearer token and credentials when a session exists', () => {
    tokenStore.setAccessToken('the-access-token');

    http.get('/api/v1/orders').subscribe();

    const request = httpTesting.expectOne('/api/v1/orders');
    expect(request.request.headers.get('Authorization')).toBe('Bearer the-access-token');
    expect(request.request.withCredentials).toBe(true);
    request.flush({});
  });

  it('sends credentials without an Authorization header when there is no session', () => {
    http.get('/api/v1/orders').subscribe();

    const request = httpTesting.expectOne('/api/v1/orders');
    expect(request.request.headers.has('Authorization')).toBe(false);
    expect(request.request.withCredentials).toBe(true);
    request.flush({});
  });

  it('does not attempt a refresh-and-retry for a 401 on the login endpoint itself', () => {
    let observedError: unknown;
    http.post('/api/v1/auth/login', {}).subscribe({ error: (error) => (observedError = error) });

    httpTesting
      .expectOne('/api/v1/auth/login')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(observedError).toBeTruthy();
    httpTesting.expectNone('/api/v1/auth/refresh');
  });

  it('refreshes and retries once on a 401 from an ordinary endpoint, then clears the session and prompts re-login on repeat failure', () => {
    tokenStore.setAccessToken('stale-token');
    const confirmationService = TestBed.inject(ConfirmationService);
    const confirmSpy = jest.spyOn(confirmationService, 'confirm');
    let observedError: unknown;
    let completed = false;

    http.get('/api/v1/orders').subscribe({
      error: (error) => (observedError = error),
      complete: () => (completed = true),
    });

    httpTesting
      .expectOne('/api/v1/orders')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    httpTesting
      .expectOne('/api/v1/auth/refresh')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    // A repeat 401 on the refresh itself clears the session and prompts the
    // user to log back in, but deliberately does not error the caller's
    // request — the interceptor returns EMPTY so `problemDetailsInterceptor`
    // doesn't also show a generic error toast on top of the confirm dialog.
    expect(observedError).toBeUndefined();
    expect(completed).toBe(true);
    expect(tokenStore.accessToken()).toBeNull();
    expect(confirmSpy).toHaveBeenCalledWith(
      expect.objectContaining({ header: 'Session Expired' }),
    );
  });
});
