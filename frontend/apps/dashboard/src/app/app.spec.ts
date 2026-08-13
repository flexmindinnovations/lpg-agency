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
    expect(shellRoute?.component).toBeTruthy();
  });

  it('contains no business routes', () => {
    // Phase 1 is foundation only. Remaining business routes each arrive in
    // their own phase behind their own plan. `orders` shipped with Order
    // Management and is deliberately no longer in this list.
    const businessPaths = ['delivery', 'accounting', 'ledger', 'complaints', 'reports'];
    const declaredTopLevel = appRoutes.map((route) => route.path ?? '');
    const declaredNested = appRoutes.flatMap(
      (route) => route.children?.map((child) => child.path ?? '') ?? [],
    );
    for (const path of businessPaths) {
      expect(declaredTopLevel).not.toContain(path);
      expect(declaredNested).not.toContain(path);
    }
  });
});
