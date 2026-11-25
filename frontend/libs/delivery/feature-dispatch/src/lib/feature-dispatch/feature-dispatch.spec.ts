import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { MessageService } from 'primeng/api';
import { ApiConfiguration, AuthService, ModuleAccessStore } from '@lpg/shared/data-access';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { FeatureDispatch } from './feature-dispatch';

const API = 'http://test/api/v1';

describe('FeatureDispatch with modules switched off', () => {
  function open(off: readonly string[]) {
    const permissions = new Set(['weighment:record']);
    TestBed.configureTestingModule({
      imports: [FeatureDispatch],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        MessageService,
        { provide: ApiConfiguration, useValue: { rootUrl: 'http://test' } },
        { provide: PERMISSION_CHECKER, useValue: signal({ permissions }) },
        { provide: AuthService, useValue: { principal: () => ({ permissions }) } },
        { provide: ModuleAccessStore, useValue: { isEnabled: (m: string) => !off.includes(m) } },
      ],
    });
    const fixture = TestBed.createComponent(FeatureDispatch);
    const component = fixture.componentInstance as unknown as {
      ngOnInit: () => void;
      onTripWarehouseChange: (id: string) => void;
    };
    component.ngOnInit();
    return { component, http: TestBed.inject(HttpTestingController) };
  }

  it('loads the scales while the Scales module is on', () => {
    const { http } = open([]);

    expect(http.match((r) => r.url === `${API}/scales`)).toHaveLength(1);
  });

  it('does not ask for scales while the Scales module is off', () => {
    const { http } = open(['scales']);

    expect(http.match((r) => r.url === `${API}/scales`)).toHaveLength(0);
  });

  it('does not ask for godown stock while the Inventory module is off', () => {
    const { component, http } = open(['inventory']);

    component.onTripWarehouseChange('w1');

    expect(http.match((r) => r.url.includes('/inventory'))).toHaveLength(0);
  });
});
