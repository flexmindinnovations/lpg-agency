import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { appRoutes } from './app.routes';

describe('App shell', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter(appRoutes)],
    }).compileComponents();
  });

  it('renders', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('exposes a skip link as the first focusable element', () => {
    // WCAG 2.2 AA (D-35): keyboard users must be able to bypass navigation.
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const skipLink: HTMLAnchorElement | null =
      fixture.nativeElement.querySelector('.shell__skip-link');
    expect(skipLink).toBeTruthy();
    expect(skipLink?.getAttribute('href')).toBe('#shell-main-content');
  });

  it('marks navigation and main content as landmarks', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('nav[aria-label="Main navigation"]')).toBeTruthy();
    expect(el.querySelector('main#shell-main-content')).toBeTruthy();
    expect(el.querySelector('header')).toBeTruthy();
  });

  it('exposes a theme trigger that opens a menu with all four theme options', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const trigger: HTMLButtonElement | null =
      fixture.nativeElement.querySelector('.shell__theme-trigger');
    expect(trigger).toBeTruthy();
    trigger?.click();
    fixture.detectChanges();

    const items: NodeListOf<HTMLElement> = document.querySelectorAll('.p-menu-item-label');
    const labels = Array.from(items).map((el) => el.textContent?.trim());
    expect(labels).toEqual(['System', 'Light', 'Dark', 'High contrast']);
  });
});

describe('Routing foundation', () => {
  it('contains no business routes', () => {
    // Phase 1 is foundation only. Customer/Inventory/Order/Delivery/Accounting
    // routes each arrive in their own phase behind their own plan.
    const businessPaths = [
      'customers',
      'orders',
      'inventory',
      'delivery',
      'accounting',
      'ledger',
      'complaints',
      'reports',
    ];
    const declared = appRoutes.map((r) => r.path ?? '');
    for (const path of businessPaths) {
      expect(declared).not.toContain(path);
    }
  });
});
