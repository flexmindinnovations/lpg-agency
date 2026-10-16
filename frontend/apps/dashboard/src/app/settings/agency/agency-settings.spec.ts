import { TestBed } from '@angular/core/testing';
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
  function render(getTenant: () => Observable<unknown>) {
    TestBed.configureTestingModule({
      providers: [{ provide: AdminTenantService, useValue: { getTenant } }],
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
});
