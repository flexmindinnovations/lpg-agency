import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

/**
 * The title block for a page — heading, optional subtitle, optional
 * back-link, and an `actions` slot.
 *
 * The dashboard shell renders page titles and page actions through two
 * separate header portals (`lpgHeaderTitlePortal` / `lpgHeaderPortal`), so
 * in that context a page puts `<lpg-page-header>` in the title portal and
 * leaves the `actions` slot empty, projecting its buttons into the actions
 * portal instead. Used standalone (not via portals) it renders the whole
 * header including actions.
 */
@Component({
  selector: 'lpg-page-header',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page-header">
      <div class="page-header__text">
        @if (backLink()) {
          <a class="page-header__back" [routerLink]="backLink()">
            <i class="pi pi-arrow-left" aria-hidden="true"></i>
            <span>{{ backLabel() }}</span>
          </a>
        }
        <h1 class="page-header__title">{{ title() }}</h1>
        @if (subtitle()) {
          <p class="page-header__subtitle">{{ subtitle() }}</p>
        }
      </div>
      <div class="page-header__actions">
        <ng-content select="[actions]" />
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .page-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--spacing-md);
        flex-wrap: wrap;
      }

      .page-header__text {
        min-inline-size: 0;
      }

      .page-header__back {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-block-end: var(--spacing-xs);
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        text-decoration: none;
      }

      .page-header__back:hover {
        color: var(--color-action-primary);
      }

      .page-header__title {
        margin: 0;
        font-size: var(--typography-heading1-font-size);
        font-weight: var(--typography-heading1-font-weight);
        line-height: var(--typography-heading1-line-height);
        letter-spacing: -0.01em;
        color: var(--color-text-primary);
      }

      .page-header__subtitle {
        margin: var(--spacing-xs) 0 0;
        font-size: var(--typography-secondary-font-size);
        color: var(--color-text-secondary);
      }

      .page-header__actions {
        display: flex;
        gap: var(--spacing-sm);
        flex-shrink: 0;
      }

      .page-header__actions:empty {
        display: none;
      }
    `,
  ],
})
export class PageHeaderComponent {
  readonly title = input.required<string>();
  readonly subtitle = input<string>('');
  /** A router link array/string; shows a back affordance above the title. */
  readonly backLink = input<unknown[] | string | null>(null);
  readonly backLabel = input<string>('Back');
}
