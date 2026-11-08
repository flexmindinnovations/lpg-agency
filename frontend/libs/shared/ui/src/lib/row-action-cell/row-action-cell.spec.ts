import { TestBed } from '@angular/core/testing';
import { RowActionCell } from './row-action-cell';

interface Row {
  name: string;
}

describe('RowActionCell', () => {
  function render(params: Record<string, unknown>): HTMLElement {
    const fixture = TestBed.createComponent(RowActionCell<Row>);
    fixture.componentInstance.agInit(params);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  const base = (onAction: (row: Row) => void) => ({
    data: { name: 'Van 2' },
    icon: 'pi pi-trash',
    label: (row: Row) => `Delete ${row.name}`,
    onAction,
  });

  it('names the row in the button label', () => {
    const button = render(base(() => undefined)).querySelector('button');

    expect(button?.getAttribute('aria-label')).toBe('Delete Van 2');
    expect(button?.getAttribute('type')).toBe('button');
  });

  it('calls back with its own row when pressed', () => {
    const onAction = jest.fn();
    const button = render(base(onAction)).querySelector('button');

    button?.click();

    expect(onAction).toHaveBeenCalledWith({ name: 'Van 2' });
  });

  it('shows no button for a row the action does not apply to', () => {
    const html = render({ ...base(() => undefined), visible: () => false });

    expect(html.querySelector('button')).toBeNull();
  });
});
