import { ChangeDetectionStrategy, Component, computed, effect, input, output, signal, type Type } from '@angular/core';
import { AgGridAngular } from 'ag-grid-angular';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef, GridApi, GridOptions, GridReadyEvent } from 'ag-grid-community';
import { SkeletonComponent } from '../skeleton/skeleton.component';

// AG Grid 33+ uses a modular architecture — features (row selection, column
// filters, etc.) are no-ops unless their module is registered first. This is
// the one place AG Grid is used (this component's own docstring below), so
// it is also the one place registration belongs, rather than scattering it
// across every app's main.ts. `AllCommunityModule` matches ADR-028's default
// (AG Grid Community, no Enterprise modules) — found via a real browser
// selection test silently failing (`AG Grid: error #200`), not a hypothetical.
ModuleRegistry.registerModules([AllCommunityModule]);

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
  /**
   * Returns the tooltip text shown on cell hover. Use when the cell displays
   * a truncated value (e.g., a short UUID prefix) and the full value should
   * be readable without opening a detail panel.
   */
  readonly tooltipValueGetter?: (value: unknown, row: TRow) => string;
  /** Extra CSS class(es) applied to every data cell in this column. */
  readonly cellClass?: string | string[] | ((value: unknown, row: TRow) => string | string[]);
  /** Custom Angular component to render the cell. */
  readonly cellRenderer?: Type<unknown>;
  /** Extra params passed to `cellRenderer`'s `agInit` (e.g. a severity map). */
  readonly cellRendererParams?: Record<string, unknown>;
  /**
   * Renders this column's cell as a real, keyboard-focusable link-styled
   * button that calls back with the row on activation — the "go to this
   * row's detail" affordance, in place of checkbox-driven row selection.
   * Setting this on any column suppresses the grid's checkbox column
   * entirely, regardless of `selectionMode`: an explicit link is a strictly
   * better affordance than "select a row, then something happens
   * elsewhere," so it takes priority rather than stacking both.
   */
  readonly onLinkClick?: (row: TRow) => void;
}

/**
 * AG Grid cell renderer backing `DataGridColumn.onLinkClick` — a real
 * `<button>` (not a fake `href="#"` anchor, since there is nowhere for it to
 * navigate) styled to read as a link, keyboard-activatable by default.
 */
@Component({
  selector: 'lpg-data-grid-link-cell',
  standalone: true,
  template: `
    <button type="button" class="lpg-data-grid-link" (click)="handleClick()">{{ value() }}</button>
  `,
  styles: [
    `
      :host {
        display: flex;
        align-items: center;
        block-size: 100%;
      }
      .lpg-data-grid-link {
        background: none;
        border: none;
        padding: 0;
        margin: 0;
        font: inherit;
        color: var(--lpg-link-color, var(--color-action-primary));
        text-decoration: underline;
        text-underline-offset: 2px;
        cursor: pointer;
        max-inline-size: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .lpg-data-grid-link:hover,
      .lpg-data-grid-link:focus-visible {
        color: var(--lpg-link-hover-color, var(--color-action-primary-hover, var(--color-action-primary)));
      }
      .lpg-data-grid-link:focus-visible {
        outline: 2px solid var(--lpg-link-color, var(--color-action-primary));
        outline-offset: 2px;
      }
    `,
  ],
})
export class DataGridLinkCell<TRow = unknown> {
  protected readonly value = signal('');
  private row: TRow | undefined;
  private onClick: ((row: TRow) => void) | undefined;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    this.value.set(params.valueFormatted ?? params.value ?? '');
    this.row = params.data as TRow;
    this.onClick = params.onLinkClick;
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }

  protected handleClick(): void {
    if (this.row !== undefined) this.onClick?.(this.row);
  }
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
  imports: [AgGridAngular, SkeletonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (loading()) {
      <div class="lpg-data-grid__skeleton">
        <lpg-skeleton variant="table" [rows]="8" [columns]="columns().length || 4" />
      </div>
    } @else {
      <ag-grid-angular
        class="lpg-data-grid"
        [rowData]="rowData()"
        [columnDefs]="columnDefs()"
        [gridOptions]="gridOptions()"
        [attr.aria-label]="ariaLabel()"
        (gridReady)="onGridReady($event)"
        (selectionChanged)="onSelectionChanged($event)"
      />
    }
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }
      .lpg-data-grid__skeleton {
        padding: var(--spacing-md);
      }
      .lpg-data-grid {
        block-size: 100%;
        inline-size: 100%;
        /* Every value comes from a design token — no raw colours or sizes. */
        --ag-row-height: var(--component-data-grid-row-height);
        --ag-header-height: var(--component-data-grid-header-height);
        --ag-cell-horizontal-padding: 12px;
        --ag-border-color: var(--component-data-grid-border-color);
        --ag-header-background-color: var(--component-data-grid-header-background);
        --ag-background-color: var(--color-surface-base);
        --ag-foreground-color: var(--color-text-primary);
        --ag-font-size: var(--typography-body-small-font-size);
        --ag-font-family: 'Inter', system-ui, -apple-system, sans-serif;
        --ag-header-font-weight: var(--typography-label-font-weight);
        --ag-header-font-size: var(--typography-caption-font-size);
        --ag-odd-row-background-color: transparent;
        --ag-row-hover-color: var(--color-surface-overlay);
        --ag-selected-row-background-color: var(--color-highlight-background);
        --ag-range-selection-border-color: var(--color-action-primary);
        --ag-borders: none;
        --ag-header-column-separator-display: none;
        --ag-row-border-width: 1px;
        --ag-row-border-color: var(--color-border-default);
        --ag-border-radius: 0;
        --ag-wrapper-border-radius: 0;
      }
      
      /* Force selected rows to use the highlight text colour so they are readable
         against the dark highlight background. Penetrate encapsulation with ::ng-deep
         because AG Grid generates the row elements. */
      ::ng-deep .lpg-data-grid .ag-row-selected {
        color: var(--color-highlight-color) !important;
        --lpg-link-color: var(--color-highlight-color);
        --lpg-link-hover-color: var(--color-highlight-color);
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
  /** Client-side pagination. `0` disables it (single scrolling list);
   *  anything else is the initial page size, with a [10, 25, 50, 100]
   *  selector. Defaults on — a long list is unusable without it. */
  readonly pageSize = input(25);

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
      // When neither flex nor width is provided by the caller, default to
      // flex: 1 so columns fill the full available width. Callers can still
      // pin a fixed pixel width or supply their own flex weight per column.
      width: column.width,
      flex: column.flex ?? (column.width === undefined ? 1 : undefined),
      type: column.numeric ? 'numericColumn' : undefined,
      cellClass: typeof column.cellClass === 'function' 
        ? (params) => (column.cellClass as any)(params.value, params.data)
        : column.cellClass,
      valueFormatter: column.valueFormatter
        ? (params) => column.valueFormatter?.(params.value, params.data as TRow) ?? ''
        : undefined,
      tooltipValueGetter: column.tooltipValueGetter
        ? (params) => column.tooltipValueGetter?.(params.value, params.data as TRow) ?? ''
        : undefined,
      cellRenderer: column.onLinkClick ? DataGridLinkCell : column.cellRenderer,
      cellRendererParams: column.onLinkClick
        ? { onLinkClick: column.onLinkClick }
        : column.cellRendererParams,
    })),
  );

  /** A link column is a strictly better "act on this row" affordance than a
   * checkbox — see `DataGridColumn.onLinkClick`'s docstring. */
  private readonly hasLinkColumn = computed(() => this.columns().some((c) => c.onLinkClick));

  protected readonly gridOptions = computed<GridOptions>(() => ({
    rowSelection:
      this.hasLinkColumn() || this.selectionMode() === 'none'
        ? undefined
        : { mode: this.selectionMode() === 'single' ? 'singleRow' : 'multiRow' },
    suppressCellFocus: false,
    // Keyboard navigation and screen-reader support are verified once here,
    // per ADR-011, rather than re-verified in every feature that shows a grid.
    ensureDomOrder: true,
    enableCellTextSelection: true,
    animateRows: true,
    // Allow columns to show native AG Grid tooltips when tooltipValueGetter
    // is supplied. A 600ms delay avoids flashing on quick mouse-overs.
    tooltipShowDelay: 600,
    tooltipHideDelay: 4000,
    // Client-side pagination — `pageSize()` of 0 turns it off.
    pagination: this.pageSize() > 0,
    paginationPageSize: this.pageSize() || 25,
    paginationPageSizeSelector: [10, 25, 50, 100],
  }));

  readonly selectionChange = output<TRow[]>();

  /**
   * AG Grid creates `cellRenderer` components dynamically via
   * `ViewContainerRef.createComponent()`, outside this component's own
   * template — and under zoneless change detection, the very first paint of
   * those components can silently lose a race against whatever else is in
   * flight when the grid's row data first arrives (reliably reproduces when
   * session/auth hydration is still resolving concurrently, e.g. right after
   * sign-in). No exception is thrown and no instance is even created —
   * `api.getCellRendererInstances()` reports zero — so there is nothing for
   * the renderer components themselves to detect or recover from; only a
   * later `api.refreshCells({ force: true })` can retroactively create them,
   * and only reliably once whatever was racing it has settled. Fixed once
   * here, centrally, rather than in every cell-renderer component: every
   * feature using this grid gets it automatically.
   */
  private gridApi: GridApi<TRow> | undefined;

  constructor() {
    effect(() => {
      this.rowData();
      this.scheduleCellRendererRefresh();
    });
  }

  protected onGridReady(event: GridReadyEvent<TRow>): void {
    this.gridApi = event.api;
    this.ready.emit();
    this.scheduleCellRendererRefresh();
  }

  protected onSelectionChanged(event: any): void {
    const selectedRows = event.api.getSelectedRows();
    this.selectionChange.emit(selectedRows as TRow[]);
  }

  /**
   * Deferred to a fresh macrotask rather than called synchronously from
   * whatever signal write triggered it — the whole point is to run *after*
   * the current burst of concurrent async work has drained, since that's
   * the condition under which AG Grid's own first-paint attempt was
   * observed to fail.
   */
  private scheduleCellRendererRefresh(): void {
    const api = this.gridApi;
    if (!api) return;
    setTimeout(() => api.refreshCells({ force: true }), 0);
  }
}
