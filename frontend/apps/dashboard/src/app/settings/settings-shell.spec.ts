import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { AuthTokenStore, PendingDevicesStore } from '@lpg/shared/data-access';
import { SettingsShell } from './settings-shell';

@Component({ template: '<p>section</p>' })
class Blank {}

const ADMIN_PERMISSIONS = [
  'tenant:read',
  'tenant:configure',
  'feature_flags:manage_tenant',
  'license:manage_tenant',
];

describe('SettingsShell', () => {
  // jsdom has no ResizeObserver, which PrimeNG's scrolling tab list uses.
  beforeAll(() => {
    globalThis.ResizeObserver ??= class {
      observe(): void {
        // no-op
      }
      unobserve(): void {
        // no-op
      }
      disconnect(): void {
        // no-op
      }
    };
  });

  async function open(url: string, permissions: string[], waiting = 0) {
    TestBed.configureTestingModule({
      providers: [
        { provide: PendingDevicesStore, useValue: { count: signal(waiting) } },
        {
          provide: AuthTokenStore,
          useValue: { principal: signal({ permissions: new Set(permissions) }) },
        },
        provideRouter([
          {
            path: 'settings',
            component: SettingsShell,
            children: [
              { path: 'account', component: Blank },
              { path: 'license', component: Blank },
              { path: 'license/devices', component: Blank },
            ],
          },
        ]),
      ],
    });
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(url, SettingsShell);
    harness.detectChanges();
    const html = harness.routeNativeElement as HTMLElement;
    return {
      html,
      badge: html.querySelector('.settings__badge')?.textContent?.trim() ?? null,
      labels: Array.from(html.querySelectorAll('p-tab')).map((a) => a.textContent?.trim()),
      dividers: html.querySelectorAll('.settings__divider').length,
    };
  }

  it('offers the Account and Agency groups to an agency admin, divided once', async () => {
    const { labels, dividers } = await open('/settings/account', ADMIN_PERMISSIONS);

    expect(dividers).toBe(1);
    expect(labels).toEqual([
      'My Profile',
      'Agency',
      'Configuration',
      'Payments',
      'Online Payments',
      'Notifications',
      'Feature Flags',
      'License',
      'Linked Devices',
    ]);
  });

  it('shows only the Account section to a role with no agency permissions', async () => {
    const { labels, dividers } = await open('/settings/account', []);

    expect(dividers).toBe(0);
    expect(labels).toEqual(['My Profile']);
  });

  it('hides individual sections the role lacks, keeping the rest of the group', async () => {
    const { labels } = await open('/settings/account', ['tenant:read', 'license:manage_tenant']);

    expect(labels).toEqual(['My Profile', 'Agency', 'License', 'Linked Devices']);
  });

  it('selects the License tab on /settings/license but not Linked Devices', async () => {
    const { html } = await open('/settings/license', ADMIN_PERMISSIONS);

    const selected = Array.from(html.querySelectorAll('p-tab[aria-selected="true"]')).map((a) =>
      a.textContent?.trim(),
    );
    expect(selected).toEqual(['License']);
  });

  it('selects Linked Devices, not License, on /settings/license/devices', async () => {
    const { html } = await open('/settings/license/devices', ADMIN_PERMISSIONS);

    const selected = Array.from(html.querySelectorAll('p-tab[aria-selected="true"]')).map((a) =>
      a.textContent?.trim(),
    );
    expect(selected).toEqual(['Linked Devices']);
  });

  it('renders the active section below the tabs', async () => {
    const { html } = await open('/settings/license/devices', ADMIN_PERMISSIONS);

    expect(html.querySelector('.settings__content')?.textContent).toContain('section');
  });

  it('shows how many phones are waiting next to Linked Devices', async () => {
    const { badge } = await open('/settings/account', ADMIN_PERMISSIONS, 3);

    expect(badge).toBe('3');
  });

  it('shows no badge when no phone is waiting', async () => {
    const { badge } = await open('/settings/account', ADMIN_PERMISSIONS, 0);

    expect(badge).toBeNull();
  });
});
