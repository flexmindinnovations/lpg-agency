import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { NEVER, of } from 'rxjs';
import { AdminTenantService, AuthService } from '@lpg/shared/data-access';
import { SetupChecklist } from './setup-checklist';

describe('SetupChecklist', () => {
  afterEach(() => localStorage.clear());

  function render(permissions: string[], complete = false, pending = false) {
    const tenantService = {
      getSetupProgress: jest.fn().mockReturnValue(
        pending
          ? NEVER
          : of({
              complete,
              steps: { branch: true, warehouse: true, cylinder_types: false, prices: false },
            }),
      ),
    };
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AdminTenantService, useValue: tenantService },
        {
          provide: AuthService,
          useValue: { principal: signal({ role: 'x', permissions: new Set(permissions) }) },
        },
      ],
    });
    const fixture = TestBed.createComponent(SetupChecklist);
    fixture.detectChanges();
    return { html: fixture.nativeElement as HTMLElement, tenantService };
  }

  it('lists the steps with links and ticks the finished ones', () => {
    const { html } = render(['tenant:configure']);

    expect(html.textContent).toContain('2 of 9 done');
    expect(html.querySelectorAll('.setup__item--done')).toHaveLength(2);
    const link = html.querySelector('a[href="/admin/cylinder-types"]');
    expect(link?.textContent).toContain('Add cylinder types');
    expect(html.querySelector('a[href="/settings/payments"]')?.textContent).toContain(
      'Set up payments',
    );
  });

  it('does not call the API for a role that cannot configure the agency', () => {
    const { html, tenantService } = render(['orders:read']);

    expect(tenantService.getSetupProgress).not.toHaveBeenCalled();
    expect(html.textContent?.trim()).toBe('');
  });

  it('hides itself once setup is complete', () => {
    const { html } = render(['tenant:configure'], true);

    expect(html.textContent?.trim()).toBe('');
  });

  it('holds the last card height while the answer is on its way, so the page does not jump', () => {
    localStorage.setItem('lpg.setup-checklist.height', '230');
    const { html } = render(['tenant:configure'], false, true);

    const reserve = html.querySelector<HTMLElement>('.setup__reserve');
    expect(reserve?.style.minBlockSize).toBe('230px');
  });

  it('reserves nothing when the card was never seen', () => {
    const { html } = render(['tenant:configure'], false, true);

    expect(html.querySelector('.setup__reserve')).toBeNull();
  });

  it('reserves nothing for a role that cannot configure the agency', () => {
    localStorage.setItem('lpg.setup-checklist.height', '230');
    const { html } = render(['orders:read'], false, true);

    expect(html.querySelector('.setup__reserve')).toBeNull();
  });

  it('drops the reservation once setup is complete', () => {
    localStorage.setItem('lpg.setup-checklist.height', '230');
    const { html } = render(['tenant:configure'], true);

    expect(html.querySelector('.setup__reserve')).toBeNull();
    expect(localStorage.getItem('lpg.setup-checklist.height')).toBeNull();
  });
});
