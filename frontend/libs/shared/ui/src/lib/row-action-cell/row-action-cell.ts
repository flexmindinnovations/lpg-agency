import { Component, signal } from '@angular/core';
import { Button } from 'primeng/button';
import { TooltipModule } from 'primeng/tooltip';

/** A row's own action, in the shape `RowActionCell` reads from `cellRendererParams`. */
export interface RowActionParams<TRow = unknown> {
  /** PrimeIcons class, e.g. `pi pi-trash`. */
  readonly icon: string;
  /** Spoken name of the button for this row, e.g. `Delete Ravi's phone`. */
  readonly label: (row: TRow) => string;
  readonly onAction: (row: TRow) => void;
  readonly severity?: 'danger' | 'secondary';
  /** Hide the button for rows it does not apply to. */
  readonly visible?: (row: TRow) => boolean;
}

/**
 * AG Grid cell renderer for a per-row icon button (delete, retry …). The
 * button is a real `<button>` with the row named in its label, so a screen
 * reader hears "Delete Ravi's phone", not "button".
 */
@Component({
  selector: 'lpg-row-action-cell',
  standalone: true,
  imports: [Button, TooltipModule],
  template: `
    @if (shown()) {
      <p-button
        size="small"
        [rounded]="true"
        [text]="true"
        [severity]="severity()"
        [icon]="icon()"
        [ariaLabel]="label()"
        [pTooltip]="label()"
        (onClick)="activate()"
      />
    }
  `,
  styles: [
    `
      :host {
        display: flex;
        align-items: center;
        block-size: 100%;
      }
    `,
  ],
})
export class RowActionCell<TRow = unknown> {
  protected readonly icon = signal('');
  protected readonly label = signal('');
  protected readonly severity = signal<'danger' | 'secondary'>('secondary');
  protected readonly shown = signal(true);
  private row: TRow | undefined;
  private onAction: ((row: TRow) => void) | undefined;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    const action = params as RowActionParams<TRow> & { data: TRow };
    this.row = action.data;
    this.onAction = action.onAction;
    this.icon.set(action.icon);
    this.severity.set(action.severity ?? 'secondary');
    this.label.set(this.row === undefined ? '' : action.label(this.row));
    this.shown.set(this.row !== undefined && (action.visible?.(this.row) ?? true));
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }

  protected activate(): void {
    if (this.row !== undefined) this.onAction?.(this.row);
  }
}
