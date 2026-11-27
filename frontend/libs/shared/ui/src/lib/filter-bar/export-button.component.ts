import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { ButtonDirective } from 'primeng/button';

/**
 * The one Export control for a list: a secondary button that says what it
 * does. It sits at the end of the list's filter bar, at the height of the
 * filters, or on the heading line of the card whose table it downloads.
 */
@Component({
  selector: 'lpg-export-button',
  standalone: true,
  imports: [ButtonDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      pButton
      type="button"
      severity="secondary"
      class="lpg-export-button"
      [disabled]="disabled()"
      (click)="export.emit()"
    >
      <i class="pi pi-download" aria-hidden="true"></i>
      <span>{{ label() }}</span>
    </button>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
      }
      .lpg-export-button {
        block-size: var(--component-control-height);
        white-space: nowrap;
      }
    `,
  ],
})
export class ExportButtonComponent {
  readonly label = input('Export CSV');
  readonly disabled = input(false);
  readonly export = output<void>();
}
