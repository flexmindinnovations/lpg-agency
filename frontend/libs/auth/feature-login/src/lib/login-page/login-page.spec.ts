import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '@lpg/shared/data-access';
import { LoginPage } from './login-page';

describe('LoginPage', () => {
  let authServiceMock: { login: jest.Mock };
  let routerMock: { navigateByUrl: jest.Mock };

  beforeEach(async () => {
    authServiceMock = { login: jest.fn() };
    routerMock = { navigateByUrl: jest.fn() };

    await TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: Router, useValue: routerMock },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap({}) } },
        },
      ],
    }).compileComponents();
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

  it('logs in and navigates to redirectTo on success', () => {
    authServiceMock.login.mockReturnValue(of(undefined));
    TestBed.overrideProvider(ActivatedRoute, {
      useValue: {
        snapshot: { queryParamMap: convertToParamMap({ redirectTo: '/orders' }) },
      },
    });

    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'staff@example.com', password: 'correct-horse-battery' });

    component['submit']();

    expect(authServiceMock.login).toHaveBeenCalledWith(
      'staff@example.com',
      'correct-horse-battery',
    );
    expect(routerMock.navigateByUrl).toHaveBeenCalledWith('/orders');
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
