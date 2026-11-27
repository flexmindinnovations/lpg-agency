import { TestBed } from '@angular/core/testing';
import { StatusChipCell } from './status-chip-cell';

describe('StatusChipCell', () => {
  function render(params: Record<string, unknown>): HTMLElement {
    const fixture = TestBed.createComponent(StatusChipCell);
    fixture.componentInstance.agInit(params);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows an on/off value as a chip using the maps', () => {
    const params = {
      labelMap: { true: 'Active', false: 'Inactive' },
      severityMap: { true: 'success', false: 'secondary' },
    };

    const on = render({ ...params, value: true });
    expect(on.querySelector('.p-tag')?.textContent).toContain('Active');
    expect(on.querySelector('.p-tag-success')).not.toBeNull();
    const off = render({ ...params, value: false });
    expect(off.querySelector('.p-tag')?.textContent).toContain('Inactive');
    expect(off.querySelector('.p-tag-secondary')).not.toBeNull();
  });

  it('shows a plain dash, not a chip, when the row has no state', () => {
    for (const value of ['—', null, '']) {
      const html = render({ value });

      expect(html.textContent?.trim()).toBe('—');
      expect(html.querySelector('.p-tag')).toBeNull();
    }
  });

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
