import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { AgGridAngular } from 'ag-grid-angular';
import type { ColDef, GridOptions } from 'ag-grid-community';

/**
 * Application-level column definition.
 *
 * Deliberately **not** AG Grid's `ColDef`. Feature libraries describe what they
 * want in application terms; this component translates that into AG Grid's API.
 * If features used `ColDef` directly, the abstraction would be cosmetic and the
 * grid would be unreplaceable in practice, whatever ADR-020 said on paper.
 */
export interface DataGridColumn<TRow = unknown> {
  /** Property on the row object. */
  readonly field: Extract<keyof TRow, string> | string;
  readonly header: string;
  readonly sortable?: boolean;
  readonly filterable?: boolean;
  readonly resizable?: boolean;
  readonly width?: number;
  readonly flex?: number;
  /** Right-align with tabular figures — the convention for numeric columns. */
  readonly numeric?: boolean;
  readonly valueFormatter?: (value: unknown, row: TRow) => string;
}

export type DataGridSelectionMode = 'none' | 'single' | 'multiple';

/**
 * The one place AG Grid is used.
 *
 * ADR-020 (amended by ADR-028) requires AG Grid to sit behind an
 * application-level component, with feature libraries never importing AG Grid
 * types or calling its APIs. That constraint is what keeps the grid
 * replaceable if licensing or product requirements change.
 *
 * **Licence:** AG Grid Community is the platform default (ADR-028). AG Grid
 * Enterprise is optional, enabled only per feature against a documented
 * requirement. Enabling it is a two-line change here — register the licence
 * key from `AG_GRID_LICENSE_KEY` and swap the module import — and touches no
 * feature code, which is precisely the point of the wrapper.
 */
@Component({
  selector: 'lpg-data-grid',
  standalone: true,
  imports: [AgGridAngular],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ag-grid-angular
      class="lpg-data-grid"
      [rowData]="rowData()"
      [columnDefs]="columnDefs()"
      [gridOptions]="gridOptions()"
      [attr.aria-label]="ariaLabel()"
      (gridReady)="onGridReady()"
    />
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }
      .lpg-data-grid {
        block-size: 100%;
        inline-size: 100%;
        /* Every value comes from a design token — no raw colours or sizes. */
        --ag-row-height: var(--component-data-grid-row-height);
        --ag-header-height: var(--component-data-grid-header-height);
        --ag-cell-horizontal-padding: var(--component-data-grid-cell-padding-x);
        --ag-border-color: var(--component-data-grid-border-color);
        --ag-header-background-color: var(--component-data-grid-header-background);
        --ag-background-color: var(--color-surface-base);
        --ag-foreground-color: var(--color-text-primary);
        --ag-font-size: var(--typography-body-small-font-size);
      }
    `,
  ],
})
export class DataGridComponent<TRow = unknown> {
  readonly rows = input.required<readonly TRow[]>();
  readonly columns = input.required<readonly DataGridColumn<TRow>[]>();
  readonly selectionMode = input<DataGridSelectionMode>('none');
  readonly loading = input(false);
  /** Required: a grid without an accessible name is unusable with a screen reader. */
  readonly ariaLabel = input.required<string>();

  readonly ready = output<void>();

  /** Mutable copy for AG Grid which expects a non-readonly array. */
  protected readonly rowData = computed(() => [...this.rows()]);

  protected readonly columnDefs = computed<ColDef[]>(() =>
    this.columns().map((column) => ({
      field: column.field,
      headerName: column.header,
      sortable: column.sortable ?? true,
      filter: column.filterable ?? false,
      resizable: column.resizable ?? true,
      width: column.width,
      flex: column.flex,
      type: column.numeric ? 'numericColumn' : undefined,
      valueFormatter: column.valueFormatter
        ? (params) => column.valueFormatter?.(params.value, params.data as TRow) ?? ''
        : undefined,
    })),
  );

  protected readonly gridOptions = computed<GridOptions>(() => ({
    rowSelection:
      this.selectionMode() === 'none'
        ? undefined
        : { mode: this.selectionMode() === 'single' ? 'singleRow' : 'multiRow' },
    suppressCellFocus: false,
    // Keyboard navigation and screen-reader support are verified once here,
    // per ADR-011, rather than re-verified in every feature that shows a grid.
    ensureDomOrder: true,
    enableCellTextSelection: true,
    animateRows: true,
  }));

  protected onGridReady(): void {
    this.ready.emit();
  }
}
