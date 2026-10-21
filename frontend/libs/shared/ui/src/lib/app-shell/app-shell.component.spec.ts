import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BreakpointObserver, type BreakpointState } from '@angular/cdk/layout';
import { of } from 'rxjs';
import { AppShellComponent } from './app-shell.component';
import type { NavGroup } from './nav-item';

const navGroups: readonly NavGroup[] = [
  { label: 'Overview', items: [{ label: 'Dashboard', icon: 'pi pi-home', route: '/' }] },
];

function render(width: 'phone' | 'tablet' | 'desktop') {
  const matches = (query: string) =>
    query.includes('767')
      ? width === 'phone'
      : query.includes('1199')
        ? width !== 'desktop'
        : false;
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      {
        provide: BreakpointObserver,
        useValue: {
          observe: (query: string) =>
            of({ matches: matches(query), breakpoints: {} } as BreakpointState),
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(AppShellComponent);
  fixture.componentRef.setInput('navGroups', navGroups);
  fixture.detectChanges();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

describe('AppShellComponent', () => {
  it('at phone width hides the sidebar behind a menu button, with labels when opened', () => {
    const { fixture, el } = render('phone');
    const sidebar = el.querySelector('#shell-sidebar') as HTMLElement;
    const menu = el.querySelector('.shell__menu-button') as HTMLButtonElement;

    expect(el.querySelector('.shell')?.classList).toContain('shell--phone');
    expect(sidebar.hasAttribute('inert')).toBe(true);
    expect(menu.getAttribute('aria-expanded')).toBe('false');

    menu.click();
    fixture.detectChanges();

    expect(sidebar.hasAttribute('inert')).toBe(false);
    expect(menu.getAttribute('aria-expanded')).toBe('true');
    expect(el.querySelector('.shell__nav-label')?.textContent).toContain('Dashboard');
    expect(el.querySelector('.shell__nav-group-label')?.textContent).toContain('Overview');

    (el.querySelector('.shell__backdrop') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(sidebar.hasAttribute('inert')).toBe(true);
  });

  it('starts as the icon rail at tablet width', () => {
    const { el } = render('tablet');
    expect(el.querySelector('.shell')?.classList).toContain('shell--collapsed');
    expect(el.querySelector('.shell__nav-label')).toBeNull();
    expect(el.querySelector('#shell-sidebar')?.hasAttribute('inert')).toBe(false);
  });

  it('shows the full sidebar on desktop', () => {
    const { el } = render('desktop');
    expect(el.querySelector('.shell')?.classList).not.toContain('shell--collapsed');
    expect(el.querySelector('.shell__nav-label')?.textContent).toContain('Dashboard');
  });
});
