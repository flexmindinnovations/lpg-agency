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
    const skipLink: HTMLAnchorElement | null = fixture.nativeElement.querySelector('.skip-link');
    expect(skipLink).toBeTruthy();
    expect(skipLink?.getAttribute('href')).toBe('#main-content');
  });

  it('marks navigation and main content as landmarks', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('nav[aria-label="Main navigation"]')).toBeTruthy();
    expect(el.querySelector('main#main-content')).toBeTruthy();
    expect(el.querySelector('header')).toBeTruthy();
  });

  it('offers system plus all three themes', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const options: NodeListOf<HTMLOptionElement> =
      fixture.nativeElement.querySelectorAll('#theme-select option');
    const values = Array.from(options).map((o) => o.value);
    expect(values).toEqual(['system', 'light', 'dark', 'high-contrast']);
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
