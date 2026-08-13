import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ProfileMenuComponent, displayNameFromEmail } from './profile-menu.component';

describe('displayNameFromEmail', () => {
  it('title-cases a dotted local-part', () => {
    expect(displayNameFromEmail('david.taylor@novastack.dev', 'Manager')).toBe('David Taylor');
  });

  it('handles underscore/hyphen separators', () => {
    expect(displayNameFromEmail('ryan_cooper@bricklane.io', 'Manager')).toBe('Ryan Cooper');
    expect(displayNameFromEmail('ryan-cooper@bricklane.io', 'Manager')).toBe('Ryan Cooper');
  });

  it('falls back to the role when there is no email', () => {
    expect(displayNameFromEmail(null, 'Branch Manager')).toBe('Branch Manager');
  });

  it('falls back to "Account" when neither email nor role is available', () => {
    expect(displayNameFromEmail(null, '')).toBe('Account');
  });
});

describe('ProfileMenuComponent', () => {
  function create() {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(ProfileMenuComponent);
    fixture.componentRef.setInput('email', 'david.taylor@novastack.dev');
    fixture.componentRef.setInput('role', 'Branch Manager');
    fixture.detectChanges();
    return fixture;
  }

  it('renders a trigger button with an accessible name derived from the email', () => {
    const fixture = create();
    const host: HTMLElement = fixture.nativeElement;
    const trigger = host.querySelector('.profile-menu__trigger');

    expect(trigger?.getAttribute('aria-label')).toBe('Account menu for David Taylor');
    expect(trigger?.getAttribute('aria-haspopup')).toBe('menu');
  });

  it('emits signOut when the Sign Out item is activated', () => {
    const fixture = create();
    const signOutSpy = jest.fn();
    fixture.componentInstance.signOut.subscribe(signOutSpy);

    (fixture.componentInstance as unknown as { onSignOutClick: () => void }).onSignOutClick();

    expect(signOutSpy).toHaveBeenCalledTimes(1);
  });

  it('lists all four theme options and sets the theme service preference on click', () => {
    const fixture = create();
    const instance = fixture.componentInstance as unknown as {
      themeOptions: ReadonlyArray<{ value: string; label: string }>;
      themePreference: () => string;
      setTheme: (value: 'system' | 'light' | 'dark' | 'high-contrast') => void;
    };

    expect(instance.themeOptions.map((option) => option.value)).toEqual([
      'system',
      'light',
      'dark',
      'high-contrast',
    ]);

    instance.setTheme('dark');
    fixture.detectChanges();
    expect(instance.themePreference()).toBe('dark');

    instance.setTheme('high-contrast');
    fixture.detectChanges();
    expect(instance.themePreference()).toBe('high-contrast');
  });
});
