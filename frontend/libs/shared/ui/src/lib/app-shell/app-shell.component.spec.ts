import { TestBed } from '@angular/core/testing';
import { provideRouter, type Routes } from '@angular/router';
import { BreakpointObserver, type BreakpointState } from '@angular/cdk/layout';
import { of } from 'rxjs';
import { AppShellComponent } from './app-shell.component';
import type { NavGroup } from './nav-item';

const navGroups: readonly NavGroup[] = [
  { label: 'Overview', items: [{ label: 'Dashboard', icon: 'pi pi-home', route: '/' }] },
];

function render(
  width: 'phone' | 'tablet' | 'desktop',
  routes: Routes = [],
  groups: readonly NavGroup[] = navGroups,
) {
  const matches = (query: string) =>
    query.includes('767')
      ? width === 'phone'
      : query.includes('1199')
        ? width !== 'desktop'
        : false;
  TestBed.configureTestingModule({
    providers: [
      provideRouter(routes),
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
  fixture.componentRef.setInput('navGroups', groups);
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
    // The text stays in the DOM (so nothing moves when the rail toggles) but is
    // hidden from assistive tech and visually.
    expect(el.querySelector('.shell__nav-label')?.getAttribute('aria-hidden')).toBe('true');
    expect(el.querySelector('#shell-sidebar')?.hasAttribute('inert')).toBe(false);
  });

  it('shows the full sidebar on desktop', () => {
    const { el } = render('desktop');
    expect(el.querySelector('.shell')?.classList).not.toContain('shell--collapsed');
    expect(el.querySelector('.shell__nav-label')?.textContent).toContain('Dashboard');
  });

  it('lights the clicked item at once, while its page is still loading, and not a second one', () => {
    const groups: readonly NavGroup[] = [
      {
        items: [
          { label: 'Home', icon: 'pi pi-home', route: '/home', exact: true },
          { label: 'Orders', icon: 'pi pi-shopping-cart', route: '/orders' },
        ],
      },
    ];
    const never = new Promise<never>(() => undefined);
    const { fixture, el } = render(
      'desktop',
      [
        { path: 'home', children: [] },
        { path: 'orders', loadComponent: () => never },
      ],
      groups,
    );
    const links = () => [...el.querySelectorAll<HTMLAnchorElement>('.shell__nav-link')];

    links()[1].click();
    fixture.detectChanges();

    expect(links().map((link) => link.classList.contains('is-active'))).toEqual([false, true]);
    expect(links()[1].getAttribute('aria-current')).toBe('page');
  });
});
