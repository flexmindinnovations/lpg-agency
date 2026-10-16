import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '@lpg/shared/data-access';
import { Profile } from './profile';

describe('Profile', () => {
  function render(principal: { email: string; role: string } | null) {
    TestBed.configureTestingModule({
      providers: [{ provide: AuthService, useValue: { principal: signal(principal) } }],
    });
    const fixture = TestBed.createComponent(Profile);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the signed-in user’s email and role', () => {
    const html = render({ email: 'admin@example.com', role: 'agency_admin' });

    expect(html.textContent).toContain('admin@example.com');
    expect(html.textContent).toContain('agency_admin');
  });

  it('falls back to placeholders when there is no principal', () => {
    const html = render(null);

    expect(html.textContent).toContain('Not set');
    expect(html.textContent).toContain('Not assigned');
  });
});
