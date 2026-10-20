import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { MessageService } from 'primeng/api';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { Observable, of, throwError } from 'rxjs';
import { AdminTenantService } from '@lpg/shared/data-access';
import { AgencySettings } from './agency-settings';

const TENANT = {
  id: 't1',
  name: 'Demo LPG Agency',
  slug: 'DEV123456',
  status: 'active',
  subscription_plan: 'standard',
  primary_contact_email: 'owner@example.com',
  country: 'IN',
};

describe('AgencySettings', () => {
  function render(getTenant: () => Observable<unknown>, permissions: string[] = []) {
    TestBed.configureTestingModule({
      providers: [
        {
          provide: AdminTenantService,
          useValue: { getTenant, listGstStates: () => of([{ code: '36', name: 'Telangana' }]) },
        },
        { provide: PERMISSION_CHECKER, useValue: signal({ permissions: new Set(permissions) }) },
        MessageService,
      ],
    });
    const fixture = TestBed.createComponent(AgencySettings);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the agency code with a sign-in hint, plus the agency details', () => {
    const html = render(() => of(TENANT));

    expect(html.querySelector('.agency-code')?.textContent?.trim()).toBe('DEV123456');
    expect(html.textContent).toContain('enter this code when signing in');
    expect(html.textContent).toContain('Demo LPG Agency');
    expect(html.textContent).toContain('owner@example.com');
  });

  it('says so, instead of showing a blank page, when the agency cannot be loaded', () => {
    const html = render(() => throwError(() => new Error('500')));

    expect(html.querySelector('[role="alert"]')?.textContent).toContain('Couldn’t load');
    expect(html.querySelector('.agency-code')).toBeNull();
  });

  it('offers the GST business profile form only to those who can configure the tenant', () => {
    expect(render(() => of(TENANT)).textContent).not.toContain('GST and invoice details');
  });

  it('pre-fills the GST business profile for a tenant admin', () => {
    const html = render(
      () =>
        of({
          ...TENANT,
          business_profile: {
            legal_name: 'Demo Gas Pvt Ltd',
            gstin: '36AAFCS4821K1Z6',
            address_line_1: '1 Main Rd',
            address_line_2: null,
            city: 'Hyderabad',
            state_code: '36',
            state_name: 'Telangana',
            pincode: '500001',
            phone: null,
          },
        }),
      ['tenant:configure'],
    );
    expect(html.textContent).toContain('GST and invoice details');
    expect((html.querySelector('#bp-gstin') as HTMLInputElement).value).toBe('36AAFCS4821K1Z6');
  });
});
