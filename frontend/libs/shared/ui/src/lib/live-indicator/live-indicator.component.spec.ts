import { TestBed } from '@angular/core/testing';
import { LiveIndicatorComponent } from './live-indicator.component';

describe('LiveIndicatorComponent', () => {
  function render(inputs: Record<string, unknown> = {}) {
    const fixture = TestBed.createComponent(LiveIndicatorComponent);
    for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('is active by default and exposes an accessible label', () => {
    const el = render();
    expect(el.querySelector('.live-indicator')?.className).toContain('live-indicator--active');
    expect(el.querySelector('.live-indicator')?.getAttribute('aria-label')).toBe('Live');
  });

  it('drops the active class when inactive', () => {
    const el = render({ active: false });
    expect(el.querySelector('.live-indicator')?.className).not.toContain('live-indicator--active');
  });

  it('renders an optional label', () => {
    const el = render({ label: '32 active' });
    expect(el.querySelector('.live-indicator__label')?.textContent).toContain('32 active');
  });
});
