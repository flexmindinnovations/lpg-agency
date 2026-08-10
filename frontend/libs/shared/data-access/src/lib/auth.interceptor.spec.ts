import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
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

  it('refreshes and retries once on a 401 from an ordinary endpoint, then clears the session on repeat failure', () => {
    tokenStore.setAccessToken('stale-token');
    let observedError: unknown;

    http.get('/api/v1/orders').subscribe({ error: (error) => (observedError = error) });

    httpTesting
      .expectOne('/api/v1/orders')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    httpTesting
      .expectOne('/api/v1/auth/refresh')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(observedError).toBeTruthy();
    expect(tokenStore.accessToken()).toBeNull();
  });
});
