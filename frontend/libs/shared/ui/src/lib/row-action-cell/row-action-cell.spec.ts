import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Tooltip } from 'primeng/tooltip';
import { RowAction, RowActionCell } from './row-action-cell';

interface Row {
  name: string;
  active?: boolean;
}

describe('RowActionCell', () => {
  function render(actions: RowAction<Row>[], data: Row | undefined = { name: 'Van 2' }) {
    const fixture = TestBed.createComponent(RowActionCell<Row>);
    fixture.componentInstance.agInit({ actions, data });
    fixture.detectChanges();
    const html = fixture.nativeElement as HTMLElement;
    return {
      html,
      buttons: () => Array.from(html.querySelectorAll('button')),
      tooltips: () =>
        fixture.debugElement
          .queryAll(By.directive(Tooltip))
          .map((element) => element.injector.get(Tooltip).content()),
    };
  }

  const remove = (onAction: (row: Row) => void = () => undefined): RowAction<Row> => ({
    icon: 'pi pi-trash',
    text: 'Delete',
    severity: 'danger',
    label: (row) => `Delete ${row.name}`,
    onAction,
  });

  it('shows each action as an icon button whose tooltip says what it does', () => {
    const { buttons, tooltips } = render([remove()]);

    expect(buttons()).toHaveLength(1);
    expect(buttons()[0].textContent?.trim()).toBe('');
    expect(buttons()[0].querySelector('.pi-trash')?.getAttribute('aria-hidden')).toBe('true');
    expect(buttons()[0].getAttribute('type')).toBe('button');
    expect(tooltips()).toEqual(['Delete']);
  });

  it('is red only when it removes or switches something off', () => {
    const open: RowAction<Row> = { ...remove(), text: 'Open', severity: undefined };

    const [plain, danger] = render([open, remove()]).buttons();

    expect(plain.classList).not.toContain('row-action--danger');
    expect(danger.classList).toContain('row-action--danger');
  });

  it('names the row in the button label, as it has no words of its own', () => {
    expect(render([remove()]).buttons()[0].getAttribute('aria-label')).toBe('Delete Van 2');
  });

  it('calls back with its own row when pressed', () => {
    const onAction = jest.fn();

    render([remove(onAction)])
      .buttons()[0]
      .click();

    expect(onAction).toHaveBeenCalledWith({ name: 'Van 2' });
  });

  it('works out the icon and tooltip from the row', () => {
    const toggle: RowAction<Row> = {
      icon: (row) => (row.active ? 'pi pi-ban' : 'pi pi-check-circle'),
      text: (row) => (row.active ? 'Deactivate' : 'Activate'),
      label: (row) => row.name,
      onAction: () => undefined,
    };

    expect(render([toggle], { name: 'A', active: true }).tooltips()).toEqual(['Deactivate']);
    const inactive = render([toggle], { name: 'B', active: false });
    expect(inactive.tooltips()).toEqual(['Activate']);
    expect(inactive.buttons()[0].querySelector('.pi-check-circle')).not.toBeNull();
  });

  it('shows only the actions that apply to the row', () => {
    const hidden = { ...remove(), text: 'Hidden', visible: () => false };

    const { tooltips } = render([hidden, remove()]);

    expect(tooltips()).toEqual(['Delete']);
  });

  it('shows nothing while the grid has no row for the cell', () => {
    const fixture = TestBed.createComponent(RowActionCell<Row>);
    fixture.componentInstance.agInit({ actions: [remove()], data: undefined });
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).querySelector('button')).toBeNull();
  });
});
