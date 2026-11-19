import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ChartCardComponent, type ChartCardState, type ChartTable } from './chart-card.component';

const TABLE: ChartTable = {
  columns: ['Stage', 'Orders'],
  rows: [
    ['Booked', 3],
    ['Delivered', 9],
  ],
};

@Component({
  standalone: true,
  imports: [ChartCardComponent],
  template: `
    <lpg-chart-card
      heading="Order pipeline"
      [state]="state()"
      [table]="table()"
      [link]="{ label: 'Orders', route: '/orders' }"
      emptyTitle="No orders yet"
    >
      <p class="projected-chart">the chart</p>
    </lpg-chart-card>
  `,
})
class HostComponent {
  readonly state = signal<ChartCardState>('ready');
  readonly table = signal<ChartTable | null>(TABLE);
}

describe('ChartCardComponent', () => {
  function render() {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    return { fixture, el, host: fixture.componentInstance };
  }

  it('shows the heading, the projected chart and a link to the module', () => {
    const { el } = render();
    expect(el.querySelector('h2')?.textContent).toContain('Order pipeline');
    expect(el.querySelector('.projected-chart')).not.toBeNull();
    expect(el.querySelector('a[href="/orders"]')?.textContent).toContain('Orders');
  });

  it('swaps the chart for the same numbers as a table, and back', () => {
    const { fixture, el } = render();
    const toggle = el.querySelector<HTMLButtonElement>('.chart-card__icon-button');
    expect(toggle?.getAttribute('aria-label')).toBe('View as table');

    toggle?.click();
    fixture.detectChanges();
    expect(el.querySelector('.projected-chart')).toBeNull();
    const cells = [...el.querySelectorAll('td')].map((td) => td.textContent?.trim());
    expect(cells).toEqual(['Booked', '3', 'Delivered', '9']);
    expect(
      el.querySelector<HTMLButtonElement>('.chart-card__icon-button')?.getAttribute('aria-label'),
    ).toBe('View as chart');

    el.querySelector<HTMLButtonElement>('.chart-card__icon-button')?.click();
    fixture.detectChanges();
    expect(el.querySelector('.projected-chart')).not.toBeNull();
  });

  it('keeps the chart area and says why when there is nothing to show', () => {
    const { fixture, el, host } = render();
    host.state.set('empty');
    fixture.detectChanges();
    expect(el.querySelector('.projected-chart')).toBeNull();
    expect(el.querySelector('lpg-empty-state')?.textContent).toContain('No orders yet');
    expect(el.querySelector('.chart-card__icon-button')).toBeNull();
  });

  it('shows a skeleton while loading, and an error that blames only this widget', () => {
    const { fixture, el, host } = render();
    host.state.set('loading');
    fixture.detectChanges();
    expect(el.querySelector('lpg-skeleton')).not.toBeNull();

    host.state.set('error');
    fixture.detectChanges();
    expect(el.querySelector('lpg-empty-state')?.textContent).toContain('could not be loaded');
    expect(el.textContent).toContain('other widgets are unaffected');
  });
});
