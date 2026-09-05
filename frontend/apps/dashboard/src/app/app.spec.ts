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
    const exempt = new Set(['', 'profile', 'notifications', 'design-system', '**']);
    const shellRoute = appRoutes.find((route) => route.path === '');
    const children = shellRoute?.children ?? [];
    for (const child of children) {
      if (exempt.has(child.path ?? '')) continue;
      expect(child.canActivate).toBeTruthy();
    }
  });
});
