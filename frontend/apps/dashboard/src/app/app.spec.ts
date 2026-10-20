import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { appRoutes } from './app.routes';

describe('App', () => {
  it('renders a bare router outlet', async () => {
    // The shell chrome moved to `ShellLayout` (see shell/shell-layout.spec.ts)
    // — `App` itself no longer assumes every route wants it.
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();

    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });
});

describe('Routing foundation', () => {
  it('routes /login outside the authenticated shell', () => {
    const loginRoute = appRoutes.find((route) => route.path === 'login');
    expect(loginRoute).toBeTruthy();
    expect(loginRoute?.canActivate).toBeUndefined();
  });

  it('gates every other route behind authGuard and ShellLayout', () => {
    const shellRoute = appRoutes.find((route) => route.path === '');
    expect(shellRoute?.canActivate).toBeTruthy();
    // ShellLayout is lazy-loaded (`loadComponent`), not eagerly imported.
    expect(shellRoute?.loadComponent).toBeTruthy();
  });

  it('gates every business route (other than profile/notifications/not-found) behind a permission guard', () => {
    // Every business module named in earlier revisions of this test
    // (delivery, accounting, ledger, orders, complaints, reports) has since
    // shipped — the invariant worth guarding isn't "these don't exist yet",
    // it's that every route which isn't explicitly exempt requires a
    // `permissionGuard`, matching `permission.guard.ts`'s own docstring that
    // the server re-enforces every one of these regardless.
    // 'design-system' is an internal component/token reference — it shows
    // no tenant data, so it carries no permission guard by design.
    // 'settings' is the frame only — its children carry their own guards (checked below).
    // 'no-access' is where permissionGuard itself sends a denied user.
    const exempt = new Set(['', 'settings', 'notifications', 'design-system', 'no-access', '**']);
    const shellRoute = appRoutes.find((route) => route.path === '');
    const children = shellRoute?.children ?? [];
    for (const child of children) {
      // Legacy-URL redirects never render anything, so they need no guard.
      if (exempt.has(child.path ?? '') || child.redirectTo) continue;
      expect(child.canActivate).toBeTruthy();
    }
  });

  it('guards every agency-wide Settings section; only Account is open to all roles', () => {
    const shellRoute = appRoutes.find((route) => route.path === '');
    const settings = shellRoute?.children?.find((child) => child.path === 'settings');
    const sections = (settings?.children ?? []).filter((child) => !child.redirectTo);
    expect(sections.length).toBeGreaterThan(0);
    for (const section of sections) {
      if (section.path === 'account') continue;
      expect(section.canActivate).toBeTruthy();
    }
  });

  it('redirects every pre-Settings URL to its new home', () => {
    const shellRoute = appRoutes.find((route) => route.path === '');
    const redirects = Object.fromEntries(
      (shellRoute?.children ?? [])
        .filter((child) => child.redirectTo)
        .map((child) => [child.path, child.redirectTo]),
    );
    expect(redirects).toEqual({
      profile: 'settings/account',
      'admin/tenant-config': 'settings/configuration',
      'admin/tenant-config/tdt-rating': 'settings/configuration/tdt-rating',
      'admin/feature-flags': 'settings/feature-flags',
      'admin/license': 'settings/license',
      'admin/license/devices': 'settings/license/devices',
    });
  });
});
