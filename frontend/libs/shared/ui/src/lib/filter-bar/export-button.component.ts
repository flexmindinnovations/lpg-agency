import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { ButtonDirective } from 'primeng/button';
import { Tooltip } from 'primeng/tooltip';

/**
 * The one Export control for a list: an icon button with a tooltip, placed
 * at the end of the list's filter bar. Same height as every other filter
 * control.
 */
@Component({
  selector: 'lpg-export-button',
  standalone: true,
  imports: [ButtonDirective, Tooltip],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      pButton
      type="button"
      severity="primary"
      [outlined]="true"
      class="lpg-export-button"
      [pTooltip]="label()"
      tooltipPosition="bottom"
      [attr.aria-label]="label()"
      [disabled]="disabled()"
      (click)="export.emit()"
    >
      <i class="pi pi-download" aria-hidden="true"></i>
    </button>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
      }
      /* Brand-coloured with a faint tint, so the download control reads as an
         action next to the grey filters. This is the one place every list's
         export button is styled. */
      .lpg-export-button {
        inline-size: var(--component-control-height);
        block-size: var(--component-control-height);
        padding: 0;
        justify-content: center;
        color: var(--color-action-primary);
        border-color: color-mix(in srgb, var(--color-action-primary) 55%, transparent);
        background: color-mix(in srgb, var(--color-action-primary) 8%, transparent);
      }
      .lpg-export-button:not(:disabled):hover {
        background: color-mix(in srgb, var(--color-action-primary) 16%, transparent);
        border-color: var(--color-action-primary);
      }
    `,
  ],
})
export class ExportButtonComponent {
  readonly label = input('Export CSV');
  readonly disabled = input(false);
  readonly export = output<void>();
}
