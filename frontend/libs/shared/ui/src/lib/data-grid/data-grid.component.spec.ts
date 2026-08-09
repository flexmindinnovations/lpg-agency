import { TestBed } from '@angular/core/testing';
import { DataGridComponent, type DataGridColumn } from './data-grid.component';

interface Row {
  readonly id: string;
  readonly quantity: number;
}

const columns: readonly DataGridColumn<Row>[] = [
  { field: 'id', header: 'ID' },
  { field: 'quantity', header: 'Quantity', numeric: true, sortable: false },
];

const rows: readonly Row[] = [
  { id: 'a', quantity: 3 },
  { id: 'b', quantity: 7 },
];

describe('DataGridComponent', () => {
  function create(overrides: Partial<{ selectionMode: string }> = {}) {
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', columns);
    fixture.componentRef.setInput('ariaLabel', 'Test grid');
    if (overrides.selectionMode) {
      fixture.componentRef.setInput('selectionMode', overrides.selectionMode);
    }
    fixture.detectChanges();
    return fixture;
  }

  it('renders the AG Grid wrapper with an accessible name', () => {
    // ADR-020: this is the one place AG Grid is used. Rendering cleanly here
    // is what proves the Community integration actually works, not just that
    // the wrapper's mapping logic compiles.
    const fixture = create();
    const host: HTMLElement = fixture.nativeElement;

    expect(host.querySelector('ag-grid-angular')).toBeTruthy();
    expect(host.querySelector('[aria-label="Test grid"]')).toBeTruthy();
  });

  it('requires an ariaLabel — a grid with no accessible name is unusable with a screen reader', () => {
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', columns);
    // ariaLabel deliberately not set.
    expect(() => fixture.detectChanges()).toThrow();
  });

  it('maps application-level columns to AG Grid column definitions', () => {
    const fixture = create();
    // Reaching into the protected computed signal is the pragmatic way to
    // verify the mapping without depending on AG Grid's internal DOM
    // structure, which is not part of this component's contract.
    const columnDefs = (
      fixture.componentInstance as unknown as { columnDefs: () => Record<string, unknown>[] }
    ).columnDefs();

    expect(columnDefs).toHaveLength(2);
    expect(columnDefs[0]).toMatchObject({ field: 'id', headerName: 'ID', sortable: true });
    expect(columnDefs[1]).toMatchObject({
      field: 'quantity',
      headerName: 'Quantity',
      sortable: false,
      type: 'numericColumn',
    });
  });

  it('defaults sortable, filterable and resizable per column when unspecified', () => {
    const fixture = create();
    const columnDefs = (
      fixture.componentInstance as unknown as { columnDefs: () => Record<string, unknown>[] }
    ).columnDefs();

    expect(columnDefs[0]).toMatchObject({ sortable: true, filter: false, resizable: true });
  });

  it('applies a custom valueFormatter through to the AG Grid column def', () => {
    const formatter = jest.fn((value: unknown) => `#${value}`);
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', [
      { field: 'quantity', header: 'Quantity', valueFormatter: formatter },
    ]);
    fixture.componentRef.setInput('ariaLabel', 'Test grid');
    fixture.detectChanges();

    const columnDefs = (
      fixture.componentInstance as unknown as {
        columnDefs: () => { valueFormatter?: (p: { value: unknown; data: Row }) => string }[];
      }
    ).columnDefs();

    const result = columnDefs[0].valueFormatter?.({ value: 3, data: rows[0] });
    expect(result).toBe('#3');
    expect(formatter).toHaveBeenCalledWith(3, rows[0]);
  });

  it('leaves row selection disabled by default', () => {
    const fixture = create();
    const gridOptions = (
      fixture.componentInstance as unknown as { gridOptions: () => { rowSelection?: unknown } }
    ).gridOptions();

    expect(gridOptions.rowSelection).toBeUndefined();
  });

  it.each([
    ['single', 'singleRow'],
    ['multiple', 'multiRow'],
  ])('maps selectionMode %s to AG Grid mode %s', (mode, expected) => {
    const fixture = create({ selectionMode: mode });
    const gridOptions = (
      fixture.componentInstance as unknown as {
        gridOptions: () => { rowSelection?: { mode: string } };
      }
    ).gridOptions();

    expect(gridOptions.rowSelection?.mode).toBe(expected);
  });

  it('emits ready when the grid signals gridReady', () => {
    const fixture = create();
    const readySpy = jest.fn();
    fixture.componentInstance.ready.subscribe(readySpy);

    (fixture.componentInstance as unknown as { onGridReady: () => void }).onGridReady();

    expect(readySpy).toHaveBeenCalledTimes(1);
  });
});
