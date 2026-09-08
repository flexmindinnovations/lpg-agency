import { TestBed } from '@angular/core/testing';
import { StarRatingComponent } from './star-rating.component';

describe('StarRatingComponent', () => {
  function render(inputs: Record<string, unknown>) {
    const fixture = TestBed.createComponent(StarRatingComponent);
    for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders a dash and "Not yet rated" when stars is null', () => {
    const el = render({ stars: null });
    expect(el.querySelector('.star-rating--empty')).toBeTruthy();
    expect(el.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe('Not yet rated');
    expect(el.textContent).toContain('—');
  });

  it('fills exactly `stars` of 5 icons and leaves the rest outlined', () => {
    const el = render({ stars: 3 });
    const icons = Array.from(el.querySelectorAll('.star-rating__star'));
    expect(icons).toHaveLength(5);
    expect(icons.filter((i) => i.classList.contains('star-rating__star--filled'))).toHaveLength(3);
    expect(icons.filter((i) => i.classList.contains('pi-star-fill'))).toHaveLength(3);
    expect(icons.filter((i) => i.classList.contains('pi-star'))).toHaveLength(2);
  });

  it('announces the rating as an accessible label', () => {
    const el = render({ stars: 4 });
    expect(el.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe('4 out of 5 stars');
  });

  it('honours a custom `max`', () => {
    const el = render({ stars: 2, max: 3 });
    expect(el.querySelectorAll('.star-rating__star')).toHaveLength(3);
  });
});
