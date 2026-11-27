import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, input, signal, type TemplateRef } from '@angular/core';

/**
 * The standard panel container for a dashboard section (a chart, a list, a
 * form group) — formalises the ad-hoc `.panel` / `.card` markup pages used
 * to hand-roll. Cards share radius / border / surface / spacing (doc §33);
 * only the projected content differs.
 *
 * A host area can flatten every card inside it by setting `--card-border`
 * (e.g. `none`) — custom properties inherit through view encapsulation, so no
 * `::ng-deep` is needed. Unset, cards have one border and no shadow.
 */
@Component({
  selector: 'lpg-section-card',
  standalone: true,
  imports: [NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (heading() || hasHeaderActions() || childActions().length) {
      <div class="section-card__header">
        @if (heading()) {
          <h2 class="section-card__heading">{{ heading() }}</h2>
        }
        <div class="section-card__header-actions">
          <ng-content select="[headerActions]" />
          @for (actions of childActions(); track actions) {
            <ng-container [ngTemplateOutlet]="actions" />
          }
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
        border: var(--card-border, var(--border-width) solid var(--component-card-border));
        border-radius: var(--radius-card);
        padding: var(--component-card-padding);
        overflow: hidden;
        /* A flex column must not squeeze a card: it would clip its content. */
        min-block-size: min-content;
      }

      /* A table in a card shows the card's own background and runs from one
         edge of the card to the other, without side borders: a box inside a
         box wastes width. Its first column lines up with the heading. */
      .section-card__body {
        --data-grid-surface: transparent;
        --data-grid-bleed: calc(-1 * var(--component-card-padding));
        --data-grid-side-border: 0;
        --data-grid-edge-padding: var(--component-card-padding);
        --component-data-grid-border-radius: 0;
      }

      /* With nothing under it, a table ends where the card does: no strip of
         card below it and no second line along the card's edge. The table may
         sit in up to two plain wrappers. */
      :host ::ng-deep .section-card__body > lpg-data-grid:last-child,
      :host ::ng-deep .section-card__body > :last-child > lpg-data-grid:last-child,
      :host ::ng-deep .section-card__body > :last-child > :last-child > lpg-data-grid:last-child {
        --data-grid-end-bleed: calc(-1 * var(--component-card-padding));
        --data-grid-end-border: 0;
      }

      /* A line divides two things: the last row of a table that ends a section
         has nothing under it to divide it from. */
      :host ::ng-deep .section-card__body table:last-child > :last-child > tr:last-child > * {
        border-block-end: 0;
      }

      .section-card__header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
      }

      .section-card__heading {
        /* A long heading wraps, so a short button stays beside it on a phone. */
        flex: 1 1 8rem;
        min-inline-size: 0;
        margin: 0;
        font-size: var(--typography-heading2-font-size);
        font-weight: var(--typography-heading2-font-weight);
        color: var(--color-text-primary);
      }

      .section-card__header-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
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

  /** Buttons that components inside the card put on its heading line. */
  protected readonly childActions = signal<readonly TemplateRef<unknown>[]>([]);

  /** Used by `lpgCardActions`. */
  addActions(template: TemplateRef<unknown>): void {
    this.childActions.update((all) => [...all, template]);
  }

  /** Used by `lpgCardActions`. */
  removeActions(template: TemplateRef<unknown>): void {
    this.childActions.update((all) => all.filter((each) => each !== template));
  }
}
