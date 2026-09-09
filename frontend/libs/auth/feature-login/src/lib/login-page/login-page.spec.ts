import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '@lpg/shared/data-access';
import { LoginPage } from './login-page';

describe('LoginPage', () => {
  let authServiceMock: { login: jest.Mock; principal: jest.Mock };
  let navigateByUrlSpy: jest.SpyInstance;

  beforeEach(async () => {
    authServiceMock = { login: jest.fn(), principal: jest.fn().mockReturnValue(null) };

    await TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        // A real router (not a bare-object mock) — the template's own
        // `routerLink` directive needs the router's real internal state
        // (routerState.root) to resolve, which a plain
        // `{ navigateByUrl: jest.fn() }` object doesn't have. Spy on the
        // real instance's navigateByUrl instead of replacing the token.
        provideRouter([]),
      ],
    }).compileComponents();

    navigateByUrlSpy = jest.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
  });

  it('renders', () => {
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('does not submit an invalid form', () => {
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();

    fixture.componentInstance['submit']();

    expect(authServiceMock.login).not.toHaveBeenCalled();
    expect(fixture.componentInstance['form'].touched).toBe(true);
  });

  it('logs in and navigates to the smart default on success', () => {
    authServiceMock.login.mockReturnValue(of(undefined));
    authServiceMock.principal.mockReturnValue({ role: 'dispatcher', permissions: new Set() });

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'staff@example.com', password: 'correct-horse-battery' });

    component['submit']();

    expect(authServiceMock.login).toHaveBeenCalledWith(
      'staff@example.com',
      'correct-horse-battery',
    );
    expect(navigateByUrlSpy).toHaveBeenCalledWith('/');
  });

  it('defaults a super_admin session to /platform', () => {
    authServiceMock.login.mockReturnValue(of(undefined));
    authServiceMock.principal.mockReturnValue({ role: 'super_admin' });

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 's_admin@lpg.com', password: 's_admin_1234' });

    component['submit']();

    expect(navigateByUrlSpy).toHaveBeenCalledWith('/platform');
  });

  it('defaults a non-platform session to /', () => {
    authServiceMock.login.mockReturnValue(of(undefined));
    authServiceMock.principal.mockReturnValue({ role: 'dispatcher', permissions: new Set() });

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'staff@example.com', password: 'correct-horse-battery' });

    component['submit']();

    expect(navigateByUrlSpy).toHaveBeenCalledWith('/');
  });

  it('defaults an ai:read-holding non-platform session to /ai-assistant', () => {
    authServiceMock.login.mockReturnValue(of(undefined));
    authServiceMock.principal.mockReturnValue({
      role: 'manager',
      permissions: new Set(['ai:read']),
    });

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'manager@example.com', password: 'correct-horse-battery' });

    component['submit']();

    expect(navigateByUrlSpy).toHaveBeenCalledWith('/ai-assistant');
  });

  it('a super_admin session still defaults to /platform even if it somehow also holds ai:read', () => {
    authServiceMock.login.mockReturnValue(of(undefined));
    authServiceMock.principal.mockReturnValue({
      role: 'super_admin',
      permissions: new Set(['ai:read']),
    });

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 's_admin@lpg.com', password: 's_admin_1234' });

    component['submit']();

    expect(navigateByUrlSpy).toHaveBeenCalledWith('/platform');
  });

  it('surfaces a friendly message for invalid credentials', () => {
    authServiceMock.login.mockReturnValue(
      throwError(() => ({ errorCode: 'INVALID_CREDENTIALS', status: 401 })),
    );

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'staff@example.com', password: 'wrong-password-here' });

    component['submit']();

    expect(component['errorMessage']()).toBe('Incorrect email or password.');
    expect(component['submitting']()).toBe(false);
  });

  it('surfaces a lockout-specific message', () => {
    authServiceMock.login.mockReturnValue(throwError(() => ({ errorCode: 'ACCOUNT_LOCKED' })));

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'staff@example.com', password: 'correct-horse-battery' });

    component['submit']();

    expect(component['errorMessage']()).toContain('temporarily locked');
  });
});
