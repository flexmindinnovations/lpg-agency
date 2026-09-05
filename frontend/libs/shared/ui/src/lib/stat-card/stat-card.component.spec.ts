import { TestBed } from '@angular/core/testing';
import { StatCardComponent } from './stat-card.component';

describe('StatCardComponent', () => {
  function render(inputs: Record<string, unknown>) {
    const fixture = TestBed.createComponent(StatCardComponent);
    for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the label and value', () => {
    const el = render({ label: 'Total Orders', value: '1,248' }).nativeElement as HTMLElement;
    expect(el.querySelector('.stat-card__label')?.textContent).toContain('Total Orders');
    expect(el.querySelector('.stat-card__value')?.textContent).toContain('1,248');
  });

  it('infers the delta direction from a leading sign', () => {
    const up = render({ label: 'x', value: 1, delta: '+12.5%' });
    expect((up.nativeElement as HTMLElement).querySelector('.stat-card__delta--up')).not.toBeNull();
    const down = render({ label: 'x', value: 1, delta: '-3.1%' });
    expect((down.nativeElement as HTMLElement).querySelector('.stat-card__delta--down')).not.toBeNull();
  });

  it('shows a skeleton instead of the value while loading', () => {
    const el = render({ label: 'x', value: 1, loading: true }).nativeElement as HTMLElement;
    expect(el.querySelector('.stat-card__value')).toBeNull();
    expect(el.querySelector('lpg-skeleton')).not.toBeNull();
  });

  it('builds a sparkline polyline from >=2 trend points', () => {
    const el = render({ label: 'x', value: 1, trend: [3, 1, 4, 1, 5] }).nativeElement as HTMLElement;
    const points = el.querySelector('.stat-card__spark polyline')?.getAttribute('points') ?? '';
    expect(points.split(' ')).toHaveLength(5);
  });

  it('omits the sparkline for a single point', () => {
    const el = render({ label: 'x', value: 1, trend: [3] }).nativeElement as HTMLElement;
    expect(el.querySelector('.stat-card__spark')).toBeNull();
  });
});
