import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * The standard panel container for a dashboard section (a chart, a list, a
 * form group) — formalises the ad-hoc `.panel` / `.card` markup pages used
 * to hand-roll. Cards share radius / border / surface / spacing (doc §33);
 * only the projected content differs.
 */
@Component({
  selector: 'lpg-section-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (heading() || hasHeaderActions()) {
      <div class="section-card__header">
        @if (heading()) {
          <h2 class="section-card__heading">{{ heading() }}</h2>
        }
        <div class="section-card__header-actions">
          <ng-content select="[headerActions]" />
        </div>
      </div>
    }
    <div class="section-card__body">
      <ng-content />
    </div>
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        background: var(--component-card-background);
        border: var(--border-width) solid var(--component-card-border);
        border-radius: var(--radius-card);
        padding: var(--component-card-padding);
        box-shadow: var(--elevation-1);
      }

      .section-card__header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-sm);
      }

      .section-card__heading {
        margin: 0;
        font-size: var(--typography-heading2-font-size);
        font-weight: var(--typography-heading2-font-weight);
        color: var(--color-text-primary);
      }

      .section-card__header-actions {
        display: flex;
        gap: var(--spacing-sm);
      }

      .section-card__header-actions:empty {
        display: none;
      }
    `,
  ],
})
export class SectionCardComponent {
  readonly heading = input<string>('');
  /** Set when projecting into the `headerActions` slot so the header row
   *  renders even without a heading. */
  readonly hasHeaderActions = input<boolean>(false);
}
