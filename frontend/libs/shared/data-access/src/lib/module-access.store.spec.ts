import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ApiConfiguration } from './generated/api-configuration';
import { ModuleAccessStore } from './module-access.store';

const URL = '/api/v1/admin/modules';

function module(key: string, enabled: boolean) {
  return { key, label: key, description: '', group: 'Operations', requires: [], enabled };
}

describe('ModuleAccessStore', () => {
  let store: ModuleAccessStore;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ApiConfiguration, useValue: { rootUrl: '' } },
      ],
    });
    store = TestBed.inject(ModuleAccessStore);
    http = TestBed.inject(HttpTestingController);
  });

  it('shows no module until the server says it is on', () => {
    expect(store.isEnabled('scales')).toBe(false);
    expect(store.loaded()).toBe(false);
  });

  it('shows only the modules the server reports as on', () => {
    store.load().subscribe();
    http.expectOne(URL).flush([module('scales', false), module('cylinder_units', true)]);

    expect(store.loaded()).toBe(true);
    expect(store.isEnabled('scales')).toBe(false);
    expect(store.isEnabled('cylinder_units')).toBe(true);
    expect(store.isEnabled('orders')).toBe(false);
  });

  it('shares one request between callers', () => {
    store.load().subscribe();
    store.ensureLoaded().subscribe();
    http.expectOne(URL).flush([]);
  });

  it('shows nothing and tries again later when the fetch fails (the API still enforces)', () => {
    store.load().subscribe();
    http.expectOne(URL).flush('nope', { status: 500, statusText: 'Server Error' });

    expect(store.loaded()).toBe(false);
    expect(store.isEnabled('scales')).toBe(false);
  });

  it('forgets the previous agency on clear', () => {
    store.load().subscribe();
    http.expectOne(URL).flush([module('scales', true)]);

    store.clear();

    expect(store.isEnabled('scales')).toBe(false);
    expect(store.loaded()).toBe(false);
  });
});
