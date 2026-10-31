import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { AuthTokenStore } from '@lpg/shared/data-access';
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
  async function open(url: string, permissions: string[]) {
    TestBed.configureTestingModule({
      providers: [
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
      labels: Array.from(html.querySelectorAll('.settings__link')).map((a) =>
        a.textContent?.trim(),
      ),
      groups: Array.from(html.querySelectorAll('.settings__group-label')).map((h) =>
        h.textContent?.trim(),
      ),
    };
  }

  it('offers the Account and Agency groups to an agency admin', async () => {
    const { labels, groups } = await open('/settings/account', ADMIN_PERMISSIONS);

    expect(groups).toEqual(['Account', 'Agency']);
    expect(labels).toEqual([
      'My Profile',
      'Agency',
      'Configuration',
      'Payments',
      'Online Payments',
      'Feature Flags',
      'License',
      'Linked Devices',
    ]);
  });

  it('shows only the Account section to a role with no agency permissions', async () => {
    const { labels, groups } = await open('/settings/account', []);

    expect(groups).toEqual(['Account']);
    expect(labels).toEqual(['My Profile']);
  });

  it('hides individual sections the role lacks, keeping the rest of the group', async () => {
    const { labels } = await open('/settings/account', ['tenant:read', 'license:manage_tenant']);

    expect(labels).toEqual(['My Profile', 'Agency', 'License', 'Linked Devices']);
  });

  it('marks the License link current on /settings/license but not Linked Devices', async () => {
    const { html } = await open('/settings/license', ADMIN_PERMISSIONS);

    const current = Array.from(html.querySelectorAll('[aria-current="page"]')).map((a) =>
      a.textContent?.trim(),
    );
    expect(current).toEqual(['License']);
  });

  it('renders the active section beside the nav', async () => {
    const { html } = await open('/settings/license/devices', ADMIN_PERMISSIONS);

    expect(html.querySelector('.settings__content')?.textContent).toContain('section');
  });
});
