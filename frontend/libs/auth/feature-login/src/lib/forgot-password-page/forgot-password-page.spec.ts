import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '@lpg/shared/data-access';
import { ForgotPasswordPage } from './forgot-password-page';

describe('ForgotPasswordPage', () => {
  let authServiceMock: { requestPasswordReset: jest.Mock };

  beforeEach(async () => {
    authServiceMock = { requestPasswordReset: jest.fn() };

    await TestBed.configureTestingModule({
      imports: [ForgotPasswordPage],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: ActivatedRoute, useValue: {} },
      ],
    }).compileComponents();
  });

  it('renders', () => {
    const fixture = TestBed.createComponent(ForgotPasswordPage);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('shows the same success state regardless of whether the account exists', () => {
    authServiceMock.requestPasswordReset.mockReturnValue(of(undefined));

    const fixture = TestBed.createComponent(ForgotPasswordPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'nobody@example.com' });

    component['submit']();

    expect(authServiceMock.requestPasswordReset).toHaveBeenCalledWith('nobody@example.com');
    expect(component['submitted']()).toBe(true);
  });

  it('does not submit an invalid email', () => {
    const fixture = TestBed.createComponent(ForgotPasswordPage);
    fixture.detectChanges();

    fixture.componentInstance['submit']();

    expect(authServiceMock.requestPasswordReset).not.toHaveBeenCalled();
  });

  it('resets the pending state on a transport failure without surfacing an error', () => {
    authServiceMock.requestPasswordReset.mockReturnValue(throwError(() => ({ status: 0 })));

    const fixture = TestBed.createComponent(ForgotPasswordPage);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component['form'].setValue({ email: 'staff@example.com' });

    component['submit']();

    expect(component['submitting']()).toBe(false);
    expect(component['submitted']()).toBe(false);
  });
});
