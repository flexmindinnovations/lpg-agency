import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * A single label/value row inside an `<lpg-detail-list>` — a stacked
 * uppercase caption label over the projected value. Formalises the
 * `.detail-item`/`.detail-label`/`.detail-value` markup that was
 * independently hand-rolled in `license-activation-page.ts`,
 * `platform-flags-page.ts`, and `license-issuance-page.ts` (three
 * near-identical copies of the same three CSS rules), plus a fourth,
 * differently-named one-off in the Profile page — one shared component
 * instead of a fifth.
 */
@Component({
  selector: 'lpg-detail-item',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="lpg-detail-item__label">{{ label() }}</span>
    <span class="lpg-detail-item__value"><ng-content /></span>
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
      }

      .lpg-detail-item__label {
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .lpg-detail-item__value {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-primary);
      }
    `,
  ],
})
export class DetailItemComponent {
  readonly label = input.required<string>();
}
