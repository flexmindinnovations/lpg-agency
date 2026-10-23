import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  output,
  signal,
  type Type,
} from '@angular/core';
import { AgGridAngular } from 'ag-grid-angular';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type {
  ColDef,
  GridApi,
  GridOptions,
  GridReadyEvent,
  GridSizeChangedEvent,
} from 'ag-grid-community';
import { ButtonDirective } from 'primeng/button';
import { Paginator, type PaginatorState } from 'primeng/paginator';
import { SkeletonComponent } from '../skeleton/skeleton.component';
import { EmptyStateComponent } from '../empty-state/empty-state.component';

/** Below this grid width, `priority: 'low'` columns are hidden (tablet/phone). */
const NARROW_GRID_PX = 720;

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
  /**
   * Narrowest this column may get before the grid scrolls sideways instead.
   * Defaults to a width that keeps the header readable, so at tablet widths
   * key columns stay legible ("Cylinde…" was the QA finding DA-21).
   */
  readonly minWidth?: number;
  /**
   * `low` columns are hidden when the grid is narrower than 720px, leaving
   * room for the columns a user scans for (number, name, status, amount).
   */
  readonly priority?: 'high' | 'low';
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
        color: var(
          --lpg-link-hover-color,
          var(--color-action-primary-hover, var(--color-action-primary))
        );
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

/** Enough for the header label plus sort icon; narrower numbers/dates. */
function defaultMinWidth(column: Pick<DataGridColumn, 'header' | 'numeric'>): number {
  const headerPx = column.header.length * 8 + 40;
  return Math.max(column.numeric ? 96 : 120, Math.min(headerPx, 200));
}

function escapeHtml(text: string): string {
  return text.replace(
    /[&<>"']/g,
    (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch] ?? ch,
  );
}

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
  imports: [AgGridAngular, SkeletonComponent, EmptyStateComponent, ButtonDirective, Paginator],
  host: {
    '[class.lpg-data-grid--auto]': 'autoHeight()',
    '[class.lpg-data-grid--bordered]': 'bordered()',
  },
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (loading()) {
      <div class="lpg-data-grid__skeleton">
        <lpg-skeleton variant="table" [rows]="8" [columns]="columns().length || 4" />
      </div>
    } @else if (error()) {
      <!-- A failed load is never shown as "no data yet" (QA DA-15). -->
      <lpg-empty-state
        tone="error"
        icon="pi pi-exclamation-triangle"
        title="Couldn't load this list"
        [description]="error() ?? ''"
      >
        <button pButton type="button" severity="secondary" actions (click)="retry.emit()">
          <i class="pi pi-refresh" aria-hidden="true"></i>
          <span>Retry</span>
        </button>
      </lpg-empty-state>
    } @else {
      <ag-grid-angular
        class="lpg-data-grid"
        [rowData]="rowData()"
        [columnDefs]="columnDefs()"
        [gridOptions]="gridOptions()"
        [attr.aria-label]="ariaLabel()"
        (gridReady)="onGridReady($event)"
        (gridSizeChanged)="onGridSizeChanged($event)"
        (selectionChanged)="onSelectionChanged($event)"
      />
    }
    @if (totalRecords() !== null && !error()) {
      <!-- Server-side paging: the pager is part of the grid card, below the
           rows, so it can never sit on top of them. -->
      <p-paginator
        class="lpg-data-grid__pager"
        [first]="(page() - 1) * serverPageSize()"
        [rows]="serverPageSize()"
        [totalRecords]="totalRecords() ?? 0"
        [rowsPerPageOptions]="[25, 50, 100]"
        [showCurrentPageReport]="true"
        [currentPageReportTemplate]="'{first}–{last} of {totalRecords} ' + recordLabel()"
        appendTo="body"
        (onPageChange)="onServerPageChange($event)"
      />
    }
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-block-size: var(--component-data-grid-min-block-size, 400px);
        block-size: 100%;
        border-radius: var(--component-data-grid-border-radius, var(--radius-md, 8px));
        overflow: hidden;
      }
      :host(.lpg-data-grid--bordered) {
        border: var(--component-data-grid-border);
      }
      /* autoHeight grids size to their content — let the host do the same. */
      :host(.lpg-data-grid--auto) {
        flex: initial;
        min-block-size: auto;
        block-size: auto;
      }
      .lpg-data-grid__skeleton {
        padding: var(--spacing-md);
      }
      .lpg-data-grid__pager {
        flex: none;
        margin-top: auto;
        border-block-start: var(--border-width, 1px) solid var(--color-border-default);
      }
      :host ::ng-deep .lpg-data-grid__pager .p-paginator {
        justify-content: flex-end;
        padding-block: var(--spacing-xs);
        background: transparent;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }
      :host ::ng-deep .lpg-data-grid .ag-styled-root {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 auto !important;
      }
      :host ::ng-deep .lpg-data-grid .ag-root-wrapper {
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
        flex: 1 1 auto !important;
      }
      :host ::ng-deep .lpg-data-grid .ag-root-wrapper-body {
        flex: 1 1 auto !important;
        min-height: 0 !important;
        height: 100% !important;
      }
      :host ::ng-deep .lpg-data-grid .ag-paging-panel {
        margin-top: auto !important;
        flex: none !important;
        border-block-start: var(--border-width, 1px) solid var(--color-border-default);
      }
      :host ::ng-deep .lpg-data-grid .lpg-data-grid__empty-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        gap: var(--spacing-xs, 6px);
        padding: var(--spacing-xl, 24px) var(--spacing-md, 16px);
        pointer-events: none;
      }
      :host ::ng-deep .lpg-data-grid .lpg-data-grid__empty-icon-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        inline-size: 3rem;
        block-size: 3rem;
        border-radius: var(--radius-full, 9999px);
        background: var(--color-surface-overlay, #f3f4f6);
        color: var(--color-text-secondary, #6b7280);
        margin-block-end: var(--spacing-xs, 4px);
      }
      :host ::ng-deep .lpg-data-grid .lpg-data-grid__empty-icon {
        font-size: 1.5rem;
      }
      :host ::ng-deep .lpg-data-grid .lpg-data-grid__empty-title {
        font-size: var(--typography-body-font-size, 14px);
        font-weight: var(--typography-label-font-weight, 600);
        color: var(--color-text-primary, #111827);
      }
      :host ::ng-deep .lpg-data-grid .lpg-data-grid__empty-desc {
        font-size: var(--typography-body-small-font-size, 13px);
        color: var(--color-text-secondary, #6b7280);
        max-inline-size: 40ch;
      }
      ::ng-deep .lpg-data-grid .lpg-data-grid__empty {
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }
      .lpg-data-grid {
        flex: 1 1 auto;
        min-block-size: 0;
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
        --ag-border-radius: var(--radius-input, 6px);
        --ag-wrapper-border-radius: var(--component-data-grid-border-radius, var(--radius-md, 8px));
        --ag-checkbox-border-radius: var(--radius-xs, 4px);
      }

      /* Force selected rows to use the highlight text colour so they are readable
         against the dark highlight background. Penetrate encapsulation with ::ng-deep
         because AG Grid generates the row elements. */
      ::ng-deep .lpg-data-grid .ag-row-selected {
        color: var(--color-highlight-color) !important;
        --lpg-link-color: var(--color-highlight-color);
        --lpg-link-hover-color: var(--color-highlight-color);
      }

      /* Extra end padding on the last column. Its cells otherwise sit 12px
         from the grid's edge, and on touch devices (tablets) the vertical
         scrollbar is an overlay that takes no layout width, so AG Grid lays
         the last column out underneath it and right-aligned values (the
         Orders "Total", ₹4500.00) lose their last characters. The header
         cell gets the same padding so its label stays aligned with the
         values below it. */
      ::ng-deep .lpg-data-grid .ag-cell.ag-column-last,
      ::ng-deep .lpg-data-grid .ag-header-cell.ag-column-last {
        padding-inline-end: var(--spacing-lg);
      }

      /* Pagination controls matching Fluent Glass design system tokens */
      ::ng-deep .lpg-data-grid .ag-paging-panel {
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }

      ::ng-deep .lpg-data-grid .ag-paging-page-size .ag-picker-field-wrapper {
        border-radius: var(--radius-input, 6px);
        border: var(--border-width, 1px) solid var(--color-border-default);
        background-color: var(--color-surface-base);
        transition: border-color var(--motion-duration-small) var(--motion-easing-standard);
      }

      ::ng-deep .lpg-data-grid .ag-paging-page-size .ag-picker-field-wrapper:focus-within {
        border-color: var(--color-border-focus);
      }

      ::ng-deep .lpg-data-grid .ag-paging-page-number {
        border-radius: var(--radius-sm, 4px);
        min-inline-size: 28px;
        min-block-size: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition:
          background-color var(--motion-duration-small) var(--motion-easing-standard),
          color var(--motion-duration-small) var(--motion-easing-standard);
      }

      ::ng-deep .lpg-data-grid .ag-paging-page-number:hover {
        background-color: var(--color-surface-overlay);
      }

      ::ng-deep .lpg-data-grid .ag-paging-page-number.ag-paging-page-number-current {
        border-radius: var(--radius-sm, 4px);
        background-color: var(--color-action-primary);
        color: var(--color-action-primary-text, #ffffff);
        font-weight: var(--typography-label-font-weight, 600);
      }

      ::ng-deep .lpg-data-grid .ag-paging-button {
        border-radius: var(--radius-sm, 4px);
        padding: var(--spacing-xs, 4px);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: background-color var(--motion-duration-small) var(--motion-easing-standard);
      }

      ::ng-deep .lpg-data-grid .ag-paging-button:not(.ag-disabled):hover {
        background-color: var(--color-surface-overlay);
      }

      /* The global :focus-visible ring (apps/dashboard/src/styles.css) uses
         an outset offset, which gets clipped here: this host has its own
         overflow:hidden for rounded corners, and AG Grid layers several
         more overflow:hidden containers inside it (root wrapper, header
         cells, paging panel) for virtualized scrolling — none of those are
         safe to loosen. An inset ring can never be clipped by an ancestor,
         so every focusable element inside the grid (cells, header sort/
         filter buttons, pagination controls) gets one scoped here instead
         of the app-wide outset default. */
      ::ng-deep .lpg-data-grid *:focus-visible {
        outline-offset: -2px;
      }
    `,
  ],
})
export class DataGridComponent<TRow = unknown> {
  readonly rows = input.required<readonly TRow[]>();
  readonly columns = input.required<readonly DataGridColumn<TRow>[]>();
  readonly selectionMode = input<DataGridSelectionMode>('none');
  readonly loading = input(false);
  readonly bordered = input(true);
  /** Required: a grid without an accessible name is unusable with a screen reader. */
  readonly ariaLabel = input.required<string>();
  /** Client-side pagination. `0` disables it (single scrolling list);
   *  anything else is the initial page size, with a [10, 25, 50, 100]
   *  selector. Defaults on — a long list is unusable without it. */
  readonly pageSize = input(25);
  /** Grow to fit the rows (up to a page) instead of filling a fixed-height
   *  host. Use inside a padded content box that has no height of its own —
   *  e.g. a report page. */
  readonly autoHeight = input(false);
  /** Free-text filter applied across every visible column's rendered value
   *  (AG Grid's own "quick filter" — no per-page filter logic needed). Only
   *  matches rows already present in `rows()`; a page whose rows come from
   *  a paginated/cursor-based endpoint needs a real server-side search
   *  instead of this. */
  readonly searchQuery = input('');
  /** A load failure message. Replaces the grid with an error state and a
   *  Retry button (emits `retry`) — never an empty "no data" grid. */
  readonly error = input<string | null>(null);
  /** Shown in the grid body when there are no rows (AG Grid's own text is
   *  "No Rows To Show"). Pages wanting a call to action use `lpg-empty-state`. */
  readonly emptyTitle = input('No data available');
  readonly emptyMessage = input('Nothing to show yet.');
  /** Server-side paging: the total row count on the server. When set, the
   *  grid shows its own pager in the card footer (client-side pagination is
   *  turned off) and emits `pageChange`; the page fetches that page. */
  readonly totalRecords = input<number | null>(null);
  /** Current 1-based page for server-side paging. */
  readonly page = input(1);
  /** Rows per page for server-side paging. */
  readonly serverPageSize = input(25);
  /** Noun in the pager's "1–25 of 80 invoices" report. */
  readonly recordLabel = input('rows');
  readonly pageChange = output<{ page: number; pageSize: number }>();

  readonly ready = output<void>();
  readonly retry = output<void>();

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
      // A flexed column without a floor squeezes to "Cylinde…" on a tablet;
      // with one, the grid scrolls sideways instead. Fixed widths are kept.
      minWidth:
        column.minWidth ?? (column.width === undefined ? defaultMinWidth(column) : undefined),
      type: column.numeric ? 'numericColumn' : undefined,
      cellClass:
        typeof column.cellClass === 'function'
          ? (params) => (column.cellClass as any)(params.value, params.data)
          : column.cellClass,
      valueFormatter: column.valueFormatter
        ? (params) => column.valueFormatter?.(params.value, params.data as TRow) ?? ''
        : undefined,
      // The quick filter (`searchQuery`) matches each column's raw field
      // value by default — not what `valueFormatter` renders. That's wrong
      // whenever the two differ (a resolved display name standing in for an
      // id, a formatted date or currency string), which is routine here: the
      // user searches for what the cell shows, not the id/ISO-string/number
      // backing it. Route quick-filter matching through the same formatter
      // so it always matches the rendered text.
      getQuickFilterText: column.valueFormatter
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
    domLayout: this.autoHeight() ? 'autoHeight' : 'normal',
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
    pagination: this.totalRecords() === null && this.pageSize() > 0,
    paginationPageSize: this.pageSize() || 25,
    paginationPageSizeSelector: [10, 25, 50, 100],
    quickFilterText: this.searchQuery(),
    overlayNoRowsTemplate: this.getEmptyOverlayTemplate(),
  }));

  readonly selectionChange = output<TRow[]>();

  private getEmptyOverlayTemplate(): string {
    return `
      <div class="lpg-data-grid__empty-container" role="status">
        <div class="lpg-data-grid__empty-icon-wrap">
          <i class="pi pi-inbox lpg-data-grid__empty-icon" aria-hidden="true"></i>
        </div>
        <div class="lpg-data-grid__empty-title">${escapeHtml(this.emptyTitle())}</div>
        <div class="lpg-data-grid__empty-desc">${escapeHtml(this.emptyMessage())}</div>
      </div>
    `;
  }

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
      const data = this.rowData();
      this.scheduleCellRendererRefresh();
      if (this.gridApi) {
        if (data.length === 0) {
          this.gridApi.showNoRowsOverlay();
        } else {
          this.gridApi.hideOverlay();
        }
      }
    });

    effect(() => {
      this.emptyTitle();
      this.emptyMessage();
      if (this.gridApi) {
        this.gridApi.setGridOption('overlayNoRowsTemplate', this.getEmptyOverlayTemplate());
        if (this.rowData().length === 0) {
          this.gridApi.showNoRowsOverlay();
        }
      }
    });

    // `[gridOptions]` is only read by ag-grid-angular at grid creation —
    // including `quickFilterText` there covers the very first render, but
    // typing afterwards never reaches the live grid through that binding.
    // AG Grid's own reactive path for an already-created grid is the
    // imperative API, same as `refreshCells` below.
    //
    // `searchQuery()` is read unconditionally, *before* the `gridApi?.`
    // guard, and bound to a local first — not inlined as the call's
    // argument. An effect only tracks signals it actually reads during a
    // given run; on the very first run `gridApi` is still undefined (the
    // grid hasn't fired `gridReady` yet), and `a?.b(c())` never evaluates
    // `c()` when `a` is nullish. Inlining the read there meant it was
    // skipped on that first run, so the effect never subscribed to
    // `searchQuery` at all and silently never fired again on any keystroke.
    effect(() => {
      const query = this.searchQuery();
      this.gridApi?.setGridOption('quickFilterText', query);
    });
  }

  protected onGridReady(event: GridReadyEvent<TRow>): void {
    this.gridApi = event.api;
    this.ready.emit();
    this.scheduleCellRendererRefresh();
    if (this.rowData().length === 0) {
      this.gridApi.showNoRowsOverlay();
    }
  }

  /** Hide `priority: 'low'` columns while the grid is narrow. */
  protected onGridSizeChanged(event: GridSizeChangedEvent<TRow>): void {
    const low = this.columns()
      .filter((c) => c.priority === 'low')
      .map((c) => c.field);
    if (low.length === 0) return;
    event.api.setColumnsVisible(low, event.clientWidth >= NARROW_GRID_PX);
  }

  /**
   * Download what the grid shows as CSV (DA-14): visible columns, current
   * sort and quick filter, every page, with each cell as rendered by its
   * `valueFormatter` (names and formatted dates rather than ids and ISO
   * strings). AG Grid Community's own exporter — no extra dependency.
   */
  exportCsv(fileName: string): void {
    this.gridApi?.exportDataAsCsv({
      fileName: fileName.endsWith('.csv') ? fileName : `${fileName}.csv`,
      processCellCallback: (params) => {
        const formatter = this.columns().find(
          (column) => column.field === params.column.getColId(),
        )?.valueFormatter;
        if (!formatter || !params.node?.data) return String(params.value ?? '');
        return formatter(params.value, params.node.data as TRow);
      },
    });
  }

  protected onServerPageChange(state: PaginatorState): void {
    const pageSize = state.rows ?? this.serverPageSize();
    this.pageChange.emit({ page: Math.floor((state.first ?? 0) / pageSize) + 1, pageSize });
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
