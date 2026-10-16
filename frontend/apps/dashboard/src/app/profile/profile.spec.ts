import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';
import { AdminTenantService, AuthService } from '@lpg/shared/data-access';
import { Profile } from './profile';

describe('Profile', () => {
  function render(getTenant: () => Observable<{ slug: string }>) {
    TestBed.configureTestingModule({
      providers: [
        {
          provide: AuthService,
          useValue: { principal: signal({ email: 'admin@example.com', role: 'agency_admin' }) },
        },
        { provide: AdminTenantService, useValue: { getTenant } },
      ],
    });
    const fixture = TestBed.createComponent(Profile);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the agency code with a sign-in hint', () => {
    const html = render(() => of({ slug: 'DEV123456' }));

    expect(html.textContent).toContain('Agency code');
    expect(html.querySelector('.agency-code')?.textContent?.trim()).toBe('DEV123456');
    expect(html.textContent).toContain('enter this code when signing in');
  });

  it('hides the agency code row when the tenant cannot be read', () => {
    const html = render(() => throwError(() => new Error('403')));

    expect(html.textContent).not.toContain('Agency code');
    expect(html.textContent).toContain('admin@example.com');
  });
});
