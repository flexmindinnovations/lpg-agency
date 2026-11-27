import { Component, signal } from '@angular/core';
import { Tooltip } from 'primeng/tooltip';

/** `primary` is the default; the colours are the status chips' own. */
export type RowActionSeverity = 'danger' | 'primary';

/** A value that is the same for every row, or worked out from the row. */
type PerRow<TRow, T> = T | ((row: TRow) => T);

/** One button in a table row's "Actions" column. */
export interface RowAction<TRow = unknown> {
  /** PrimeIcons class, e.g. `pi pi-trash`. */
  readonly icon: PerRow<TRow, string>;
  /** What the button does, e.g. `Delete`. Shown as its tooltip. */
  readonly text: PerRow<TRow, string>;
  /** Spoken name of the button for this row, e.g. `Delete Ravi's phone`.
   *  Starts with `text`, so voice control can find what the tooltip says. */
  readonly label: (row: TRow) => string;
  readonly onAction: (row: TRow) => void;
  /** `danger` for anything that removes or switches something off. */
  readonly severity?: PerRow<TRow, RowActionSeverity>;
  /** Hide the button for rows it does not apply to. */
  readonly visible?: (row: TRow) => boolean;
}

/** What `RowActionCell` reads from `cellRendererParams`. */
export interface RowActionParams<TRow = unknown> {
  readonly actions: readonly RowAction<TRow>[];
}

interface RowButton {
  readonly icon: string;
  readonly text: string;
  readonly label: string;
  readonly severity: RowActionSeverity;
  readonly run: () => void;
}

function forRow<TRow, T>(value: PerRow<TRow, T>, row: TRow): T {
  return typeof value === 'function' ? (value as (row: TRow) => T)(row) : value;
}

/**
 * AG Grid cell renderer for a table row's actions: an icon button for each,
 * tinted like a status chip, with a tooltip that says what it does. Use it
 * through `rowActionsColumn` in `@lpg/shared/ui/data-grid`, the one way a
 * table offers row actions.
 */
@Component({
  selector: 'lpg-row-action-cell',
  standalone: true,
  imports: [Tooltip],
  template: `
    @for (button of buttons(); track button.text) {
      <button
        type="button"
        class="row-action"
        [class.row-action--danger]="button.severity === 'danger'"
        [attr.aria-label]="button.label"
        [pTooltip]="button.text"
        tooltipPosition="top"
        tooltipEvent="both"
        appendTo="body"
        (click)="button.run()"
      >
        <i [class]="button.icon" aria-hidden="true"></i>
      </button>
    }
  `,
  styles: [
    `
      /* Inline, like a chip: the cell's line height centres it in the row. The
         grid's wrapper is only as tall as its content, so a block that fills it
         would sit at the top of the row. */
      :host {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        vertical-align: middle;
      }

      /* 28px: above the 24px minimum target size (WCAG 2.2, 2.5.8). */
      .row-action {
        display: inline-flex;
        flex: none;
        align-items: center;
        justify-content: center;
        inline-size: 1.75rem;
        block-size: 1.75rem;
        padding: 0;
        border: var(--border-width) solid transparent;
        border-radius: var(--radius-sm);
        background: var(--component-chip-info-background);
        color: var(--component-chip-info-text);
        font-size: var(--typography-body-small-font-size);
        cursor: pointer;
      }

      .row-action--danger {
        background: var(--component-chip-danger-background);
        color: var(--component-chip-danger-text);
      }

      /* Like the chips: high contrast has no tint, so it draws the edge. */
      :host-context([data-theme='high-contrast']) .row-action,
      .row-action:hover {
        border-color: currentcolor;
      }

      .row-action:focus-visible {
        outline: var(--component-focus-ring-width) solid var(--color-action-primary);
        outline-offset: 1px;
      }
    `,
  ],
})
export class RowActionCell<TRow = unknown> {
  protected readonly buttons = signal<readonly RowButton[]>([]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    const { actions, data } = params as RowActionParams<TRow> & { data: TRow | undefined };
    if (data === undefined) {
      this.buttons.set([]);
      return;
    }
    this.buttons.set(
      actions
        .filter((action) => action.visible?.(data) ?? true)
        .map((action) => ({
          icon: forRow(action.icon, data),
          text: forRow(action.text, data),
          label: action.label(data),
          severity: forRow(action.severity ?? 'primary', data),
          run: () => action.onAction(data),
        })),
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}
