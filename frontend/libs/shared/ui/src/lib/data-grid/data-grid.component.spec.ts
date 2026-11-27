import { TestBed } from '@angular/core/testing';
import {
  DataGridComponent,
  DataGridLinkCell,
  rowActionsColumn,
  type DataGridColumn,
} from './data-grid.component';
import { RowActionCell } from '../row-action-cell/row-action-cell';

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
  function create(overrides: Partial<{ selectionMode: string; pageSize: number }> = {}) {
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', columns);
    fixture.componentRef.setInput('ariaLabel', 'Test grid');
    if (overrides.selectionMode) {
      fixture.componentRef.setInput('selectionMode', overrides.selectionMode);
    }
    if (overrides.pageSize !== undefined) {
      fixture.componentRef.setInput('pageSize', overrides.pageSize);
    }
    fixture.detectChanges();
    return fixture;
  }

  const gridOptionsOf = (fixture: ReturnType<typeof create>) =>
    (
      fixture.componentInstance as unknown as {
        gridOptions: () => {
          pagination?: boolean;
          paginationPageSize?: number;
          paginationPageSizeSelector?: number[];
        };
      }
    ).gridOptions();

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
      cellStyle: { fontVariantNumeric: 'tabular-nums' },
    });
    // Every column aligns the same way, numbers included.
    expect(columnDefs.map((def) => def['type'])).toEqual([undefined, undefined]);
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

  it('paginates by default at 10 rows per page', () => {
    const options = gridOptionsOf(create());
    expect(options.pagination).toBe(true);
    expect(options.paginationPageSize).toBe(10);
    expect(options.paginationPageSizeSelector).toEqual([10, 25, 50, 100]);
  });

  it('honours a custom page size', () => {
    expect(gridOptionsOf(create({ pageSize: 50 })).paginationPageSize).toBe(50);
  });

  it('disables pagination when pageSize is 0', () => {
    expect(gridOptionsOf(create({ pageSize: 0 })).pagination).toBe(false);
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
    const fakeEvent = { api: { refreshCells: jest.fn() } };

    (
      fixture.componentInstance as unknown as {
        onGridReady: (event: typeof fakeEvent) => void;
      }
    ).onGridReady(fakeEvent);

    expect(readySpy).toHaveBeenCalledTimes(1);
  });

  it('shows an error state with Retry instead of an empty grid when loading failed', () => {
    const fixture = create();
    fixture.componentRef.setInput('error', 'The server did not respond.');
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const retrySpy = jest.fn();
    fixture.componentInstance.retry.subscribe(retrySpy);

    expect(el.querySelector('ag-grid-angular')).toBeNull();
    expect(el.textContent).toContain("Couldn't load this list");
    expect(el.textContent).toContain('The server did not respond.');
    (el.querySelector('button') as HTMLButtonElement).click();
    expect(retrySpy).toHaveBeenCalledTimes(1);
  });

  it('gives flexed columns a readable minimum width but keeps fixed widths', () => {
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', [
      { field: 'id', header: 'Cylinder type' },
      { field: 'quantity', header: 'Qty', width: 80 },
    ]);
    fixture.componentRef.setInput('ariaLabel', 'Test grid');
    fixture.detectChanges();
    const defs = (
      fixture.componentInstance as unknown as { columnDefs: () => { minWidth?: number }[] }
    ).columnDefs();
    expect(defs[0].minWidth).toBeGreaterThanOrEqual(120);
    expect(defs[1].minWidth).toBeUndefined();
  });

  it('hides low-priority columns when the grid is narrow', () => {
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', [
      { field: 'id', header: 'ID' },
      { field: 'quantity', header: 'Quantity', priority: 'low' },
    ]);
    fixture.componentRef.setInput('ariaLabel', 'Test grid');
    fixture.detectChanges();
    const setColumnsVisible = jest.fn();
    const sized = (clientWidth: number) =>
      (
        fixture.componentInstance as unknown as {
          onGridSizeChanged: (e: unknown) => void;
        }
      ).onGridSizeChanged({ clientWidth, api: { setColumnsVisible } });

    sized(600);
    sized(1000);
    expect(setColumnsVisible).toHaveBeenNthCalledWith(1, ['quantity'], false);
    expect(setColumnsVisible).toHaveBeenNthCalledWith(2, ['quantity'], true);
  });

  it('drops only as many low-priority columns as it takes to fit', () => {
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', [
      { field: 'name', header: 'Name', minWidth: 400 },
      { field: 'first', header: 'First', width: 200, priority: 'low' },
      { field: 'second', header: 'Second', minWidth: 200, priority: 'low' },
      { field: 'actions', header: 'Actions', width: 150 },
    ]);
    fixture.componentRef.setInput('ariaLabel', 'Test grid');
    fixture.detectChanges();
    const setColumnsVisible = jest.fn();
    const sized = (clientWidth: number) => {
      setColumnsVisible.mockClear();
      (
        fixture.componentInstance as unknown as {
          onGridSizeChanged: (e: unknown) => void;
        }
      ).onGridSizeChanged({ clientWidth, api: { setColumnsVisible } });
      return setColumnsVisible.mock.calls;
    };

    // All 950px fit.
    expect(sized(960)).toEqual([[['first', 'second'], true]]);
    // Wider than the narrow limit, but not wide enough: the last one goes.
    expect(sized(800)).toEqual([
      [['first'], true],
      [['second'], false],
    ]);
    expect(sized(740)).toEqual([[['first', 'second'], false]]);
  });
});

describe('rowActionsColumn', () => {
  const action = {
    icon: 'pi pi-trash',
    text: 'Delete',
    label: (row: Row) => `Delete ${row.id}`,
    onAction: () => undefined,
  };

  it('is an "Actions" column of buttons that cannot be sorted', () => {
    expect(rowActionsColumn<Row>([action])).toMatchObject({
      field: 'actions',
      header: 'Actions',
      sortable: false,
      cellRenderer: RowActionCell,
      cellRendererParams: { actions: [action] },
    });
  });

  it('leaves the buttons out of a CSV download', () => {
    const fixture = TestBed.createComponent(DataGridComponent<Row>);
    fixture.componentRef.setInput('rows', rows);
    fixture.componentRef.setInput('columns', [...columns, rowActionsColumn<Row>([action])]);
    fixture.componentRef.setInput('ariaLabel', 'Test grid');
    fixture.detectChanges();
    const exportDataAsCsv = jest.fn();
    const shown = ['id', 'quantity', 'actions'].map((id) => ({ getColId: () => id }));
    (fixture.componentInstance as unknown as { gridApi: unknown }).gridApi = {
      exportDataAsCsv,
      getAllDisplayedColumns: () => shown,
    };

    fixture.componentInstance.exportCsv('stock');

    expect(exportDataAsCsv.mock.calls[0][0]).toMatchObject({
      fileName: 'stock.csv',
      columnKeys: ['id', 'quantity'],
    });
  });
});

describe('DataGridLinkCell', () => {
  function buttons(valueFormatted: string): number {
    const fixture = TestBed.createComponent(DataGridLinkCell);
    fixture.componentInstance.agInit({ valueFormatted, data: {} });
    fixture.detectChanges();
    return (fixture.nativeElement as HTMLElement).querySelectorAll('button').length;
  }

  it('renders no button for a row with no action', () => {
    expect(buttons('')).toBe(0);
  });

  it('renders one for a row with an action', () => {
    expect(buttons('Set GST')).toBe(1);
  });
});
