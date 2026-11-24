import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { NEVER, of } from 'rxjs';
import { AdminTenantService, AuthService } from '@lpg/shared/data-access';
import { SetupChecklist } from './setup-checklist';

const ALL_DONE = {
  branch: true,
  warehouse: true,
  cylinder_types: true,
  prices: true,
  gst: true,
  payments: true,
  staff: true,
  drivers: true,
  vehicles: true,
};

describe('SetupChecklist', () => {
  function render(permissions: string[], complete = false, pending = false) {
    const tenantService = {
      getSetupProgress: jest.fn().mockReturnValue(
        pending
          ? NEVER
          : of({
              complete,
              steps: complete ? ALL_DONE : { ...ALL_DONE, cylinder_types: false, prices: false },
            }),
      ),
    };
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AdminTenantService, useValue: tenantService },
        {
          provide: AuthService,
          useValue: {
            principal: signal({ role: 'x', userId: 'u1', permissions: new Set(permissions) }),
          },
        },
      ],
    });
    const fixture = TestBed.createComponent(SetupChecklist);
    fixture.detectChanges();
    return {
      html: fixture.nativeElement as HTMLElement,
      host: fixture.nativeElement as HTMLElement,
      fixture,
      tenantService,
    };
  }

  it('lists the steps with links and ticks the finished ones', () => {
    const { html } = render(['tenant:configure']);

    expect(html.textContent).toContain('7 of 9 done');
    expect(html.querySelectorAll('.setup__item--done')).toHaveLength(7);
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

  it('shows while any single step is still to do', () => {
    const { html } = render(['tenant:configure']);

    expect(html.textContent).toContain('Finish setting up your agency');
  });

  it('hides itself once every step is done', () => {
    const { html } = render(['tenant:configure'], true);

    expect(html.textContent?.trim()).toBe('');
  });

  it('reserves no room while the answer is on its way, so the cards below are not pushed', () => {
    const { host } = render(['tenant:configure'], false, true);

    expect(host.classList).not.toContain('setup--shown');
    expect(host.children).toHaveLength(0);
  });

  it('shows the card closed first, then opens it so the move is animated', async () => {
    const { host, fixture } = render(['tenant:configure']);

    expect(host.classList).toContain('setup--shown');
    expect(host.classList).not.toContain('setup--open');

    await new Promise((resolve) => setTimeout(resolve, 50));
    fixture.detectChanges();
    expect(host.classList).toContain('setup--open');
  });

  it('shows the card at once on a revisit, with no entrance', () => {
    const first = render(['tenant:configure']);
    first.fixture.destroy();

    const second = TestBed.createComponent(SetupChecklist);
    second.detectChanges();
    const host = second.nativeElement as HTMLElement;

    expect(host.classList).toContain('setup--shown');
    expect(host.classList).toContain('setup--open');
  });

  it('shows nothing for a role that cannot configure the agency', () => {
    const { host } = render(['orders:read'], false, true);

    expect(host.classList).not.toContain('setup--shown');
  });
});
