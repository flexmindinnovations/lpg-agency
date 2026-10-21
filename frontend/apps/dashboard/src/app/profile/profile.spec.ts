import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { AuthService, MyProfileService, NotifyService } from '@lpg/shared/data-access';
import { Profile } from './profile';

describe('Profile', () => {
  let profileService: {
    getProfile: jest.Mock;
    updateProfile: jest.Mock;
    changePassword: jest.Mock;
  };
  let notify: { success: jest.Mock; error: jest.Mock };

  function render(principal: { email: string; role: string } | null) {
    profileService = {
      getProfile: jest.fn().mockReturnValue(
        of({
          user_id: 'u1',
          email: 'admin@example.com',
          role: 'agency_admin',
          display_name: 'Ravi Kumar',
          contact_phone: '+91 98490 12345',
        }),
      ),
      updateProfile: jest.fn(),
      changePassword: jest.fn(),
    };
    notify = { success: jest.fn(), error: jest.fn() };
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: { principal: signal(principal) } },
        { provide: MyProfileService, useValue: profileService },
        { provide: NotifyService, useValue: notify },
      ],
    });
    const fixture = TestBed.createComponent(Profile);
    fixture.detectChanges();
    return fixture;
  }

  it('shows the email, a readable role and the saved details', () => {
    const fixture = render({ email: 'admin@example.com', role: 'agency_admin' });
    const html = fixture.nativeElement as HTMLElement;

    expect(html.textContent).toContain('admin@example.com');
    expect(html.textContent).toContain('Agency Admin');
    expect(html.textContent).not.toContain('agency_admin');
    expect(fixture.componentInstance['detailsForm'].getRawValue()).toEqual({
      displayName: 'Ravi Kumar',
      contactPhone: '+91 98490 12345',
    });
  });

  it('falls back to placeholders when there is no principal', () => {
    const html = render(null).nativeElement as HTMLElement;

    expect(html.textContent).toContain('Not set');
    expect(html.textContent).toContain('Not assigned');
  });

  it('saves name and phone', () => {
    const fixture = render({ email: 'a@example.com', role: 'manager' });
    profileService.updateProfile.mockReturnValue(
      of({
        user_id: 'u1',
        email: null,
        role: 'manager',
        display_name: 'Asha',
        contact_phone: null,
      }),
    );
    const component = fixture.componentInstance;
    component['detailsForm'].setValue({ displayName: ' Asha ', contactPhone: '' });

    component['saveDetails']();

    expect(profileService.updateProfile).toHaveBeenCalledWith({
      display_name: 'Asha',
      contact_phone: null,
    });
    expect(notify.success).toHaveBeenCalled();
  });

  it('changes the password and explains a wrong current password', () => {
    const fixture = render({ email: 'a@example.com', role: 'manager' });
    const component = fixture.componentInstance;
    const fill = () =>
      component['passwordForm'].setValue({
        currentPassword: 'old',
        newPassword: 'a brand new passphrase',
        confirmPassword: 'a brand new passphrase',
      });

    profileService.changePassword.mockReturnValue(
      throwError(() => ({
        errorCode: 'VALIDATION_ERROR',
        fieldErrors: { current_password: ['x'] },
      })),
    );
    fill();
    component['changePassword']();
    expect(component['passwordError']()).toBe('Your current password is not correct.');

    profileService.changePassword.mockReturnValue(of(undefined));
    fill();
    component['changePassword']();
    expect(profileService.changePassword).toHaveBeenLastCalledWith('old', 'a brand new passphrase');
    expect(notify.success).toHaveBeenCalledWith('Your password was updated.');
  });

  it('does not submit a too-short new password', () => {
    const fixture = render({ email: 'a@example.com', role: 'manager' });
    const component = fixture.componentInstance;
    component['passwordForm'].setValue({
      currentPassword: 'old',
      newPassword: 'short',
      confirmPassword: 'short',
    });

    component['changePassword']();

    expect(profileService.changePassword).not.toHaveBeenCalled();
  });
});
