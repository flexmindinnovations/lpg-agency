import { TestBed } from '@angular/core/testing';
import { SkeletonComponent } from './skeleton.component';

describe('SkeletonComponent', () => {
  function render(inputs: Record<string, unknown> = {}) {
    const fixture = TestBed.createComponent(SkeletonComponent);
    for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders a single bar for the block variant', () => {
    const el = render();
    expect(el.querySelectorAll('.skeleton-bar')).toHaveLength(1);
  });

  it('renders one bar per line for the text variant', () => {
    const el = render({ variant: 'text', lines: 4 });
    expect(el.querySelectorAll('.skeleton-bar')).toHaveLength(4);
  });

  it('renders a header row plus body rows for the table variant', () => {
    const el = render({ variant: 'table', rows: 3, columns: 5 });
    // 4 rows (1 head + 3 body) x 5 columns
    expect(el.querySelectorAll('.skeleton-bar')).toHaveLength(20);
  });

  it('carries an assistive-tech loading announcement', () => {
    const el = render();
    expect(el.querySelector('.skeleton-sr')?.textContent).toContain('Loading');
  });
});
