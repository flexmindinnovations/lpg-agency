import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Vertical stack of `<lpg-detail-item>` rows — the layout half of the
 * shared detail-item primitive (see `detail-item.component.ts`'s own
 * doc comment for the duplication this replaces). Deliberately plain,
 * no card chrome of its own: wrap it in `<lpg-section-card>` for a
 * standalone page's "modern touch" card look, or drop it straight into
 * a drawer's own content area where the drawer already supplies the
 * surface.
 */
@Component({
  selector: 'lpg-detail-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<ng-content />`,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
      }
    `,
  ],
})
export class DetailListComponent {}
