import { TestBed } from '@angular/core/testing';
import { EmptyStateComponent } from './empty-state.component';

describe('EmptyStateComponent', () => {
  function render(inputs: Record<string, unknown>) {
    const fixture = TestBed.createComponent(EmptyStateComponent);
    for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders the title and description', () => {
    const el = render({ title: 'No deliveries scheduled', description: 'Nothing for this date.' });
    expect(el.querySelector('.empty-state__title')?.textContent).toContain('No deliveries scheduled');
    expect(el.querySelector('.empty-state__description')?.textContent).toContain('Nothing for this date.');
  });

  it('defaults to a neutral inbox icon, and a danger icon for the error tone', () => {
    expect(render({ title: 'x' }).querySelector('.empty-state__icon')?.className).toContain('pi-inbox');
    const err = render({ title: 'Unable to load orders', tone: 'error' });
    expect(err.querySelector('.empty-state')?.className).toContain('empty-state--error');
    expect(err.querySelector('.empty-state__icon')?.className).toContain('pi-exclamation-triangle');
  });

  it('honours an explicit icon override', () => {
    const el = render({ title: 'x', icon: 'pi pi-calendar' });
    expect(el.querySelector('.empty-state__icon')?.className).toContain('pi-calendar');
  });
});
