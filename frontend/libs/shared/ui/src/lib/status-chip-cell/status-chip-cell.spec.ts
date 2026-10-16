import { TestBed } from '@angular/core/testing';
import { StatusChipCell } from './status-chip-cell';

describe('StatusChipCell', () => {
  function render(params: Record<string, unknown>): HTMLElement {
    const fixture = TestBed.createComponent(StatusChipCell);
    fixture.componentInstance.agInit(params);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('falls back to sentence case when there is no label map', () => {
    expect(render({ value: 'walk_in' }).textContent).toContain('Walk in');
  });

  it('uses the label map when it names the value', () => {
    const html = render({ value: 'staff', labelMap: { staff: 'Dashboard' } });

    expect(html.textContent).toContain('Dashboard');
    expect(html.textContent).not.toContain('Staff');
  });

  it('falls back to sentence case for a value the label map does not name', () => {
    expect(render({ value: 'phone', labelMap: { staff: 'Dashboard' } }).textContent).toContain(
      'Phone',
    );
  });
});
