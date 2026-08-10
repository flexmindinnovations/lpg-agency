import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '@lpg/shared/data-access';
import { ResetPasswordPage } from './reset-password-page';

function configure(queryParams: Record<string, string>, authServiceMock: unknown) {
  return TestBed.configureTestingModule({
    imports: [ResetPasswordPage],
    providers: [
      { provide: AuthService, useValue: authServiceMock },
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { queryParamMap: convertToParamMap(queryParams) } },
      },
    ],
  }).compileComponents();
}

describe('ResetPasswordPage', () => {
  it('shows an invalid-link state when no token is present', async () => {
    await configure({}, { confirmPasswordReset: jest.fn() });

    const fixture = TestBed.createComponent(ResetPasswordPage);
    fixture.detectChanges();

    expect(fixture.componentInstance['resetToken']()).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Invalid link');
  });

  it('confirms the reset and shows success', async () => {
    const authServiceMock = { confirmPasswordReset: jest.fn().mockReturnValue(of(undefined)) };
    await configure({ token: 'a-valid-token' }, authServiceMock);

    const fixture = TestBed.createComponent(ResetPasswordPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({
      newPassword: 'a-new-strong-password',
      confirmPassword: 'a-new-strong-password',
    });

    component['submit']();

    expect(authServiceMock.confirmPasswordReset).toHaveBeenCalledWith(
      'a-valid-token',
      'a-new-strong-password',
    );
    expect(component['succeeded']()).toBe(true);
  });

  it('rejects a submission when the two passwords do not match', async () => {
    const authServiceMock = { confirmPasswordReset: jest.fn() };
    await configure({ token: 'a-valid-token' }, authServiceMock);

    const fixture = TestBed.createComponent(ResetPasswordPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({
      newPassword: 'a-new-strong-password',
      confirmPassword: 'does-not-match-it',
    });

    component['submit']();

    expect(authServiceMock.confirmPasswordReset).not.toHaveBeenCalled();
    expect(component['mismatch']()).toBe(true);
  });

  it('surfaces an expired-token message', async () => {
    const authServiceMock = {
      confirmPasswordReset: jest
        .fn()
        .mockReturnValue(throwError(() => ({ errorCode: 'RESET_TOKEN_EXPIRED' }))),
    };
    await configure({ token: 'an-expired-token' }, authServiceMock);

    const fixture = TestBed.createComponent(ResetPasswordPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({
      newPassword: 'a-new-strong-password',
      confirmPassword: 'a-new-strong-password',
    });

    component['submit']();

    expect(component['errorMessage']()).toContain('expired');
  });
});
