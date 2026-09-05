import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { PageHeaderComponent } from './page-header.component';

describe('PageHeaderComponent', () => {
  function render(inputs: Record<string, unknown>) {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(PageHeaderComponent);
    for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders the title as an h1 and an optional subtitle', () => {
    const el = render({ title: 'Agency Overview', subtitle: "Today's operational data" });
    expect(el.querySelector('h1.page-header__title')?.textContent).toContain('Agency Overview');
    expect(el.querySelector('.page-header__subtitle')?.textContent).toContain("Today's operational data");
  });

  it('omits the subtitle and the back link when not provided', () => {
    const el = render({ title: 'Orders' });
    expect(el.querySelector('.page-header__subtitle')).toBeNull();
    expect(el.querySelector('.page-header__back')).toBeNull();
  });

  it('shows a back affordance when backLink is set', () => {
    const el = render({ title: 'Order detail', backLink: '/orders', backLabel: 'All orders' });
    const back = el.querySelector('.page-header__back');
    expect(back?.textContent).toContain('All orders');
    expect(back?.getAttribute('href')).toBe('/orders');
  });
});
