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
      severity="secondary"
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
      .lpg-export-button {
        inline-size: var(--component-control-height);
        block-size: var(--component-control-height);
        padding: 0;
        justify-content: center;
      }
    `,
  ],
})
export class ExportButtonComponent {
  readonly label = input('Export CSV');
  readonly disabled = input(false);
  // eslint-disable-next-line @angular-eslint/no-output-native -- "export" reads naturally here and is not a DOM event
  readonly export = output<void>();
}
