import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { InfoTipComponent } from '../info-tip/info-tip.component';

/**
 * The title block for a page — heading, info button for the subtitle, optional
 * back-link, and an `actions` slot.
 *
 * The dashboard shell portals page titles into its own fixed top bar via
 * `lpgHeaderTitlePortal` — a page puts `<lpg-page-header>` there. Primary
 * page actions (Add/Register/etc.) do **not** go through a header portal —
 * they render inline in the page's own content, in its `.data-toolbar__actions`
 * row alongside Search/Filter/Export, so they stay next to the data they
 * act on rather than floating in the global header, disconnected from it.
 * Used standalone (not via a title portal) this component renders the
 * whole header including its own `actions` slot, for a page that isn't
 * shell-wrapped.
 */
@Component({
  selector: 'lpg-page-header',
  standalone: true,
  imports: [RouterLink, InfoTipComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  // `title` is also an HTML attribute: left on the element, the browser shows
  // its own tooltip over the whole header.
  host: { '[attr.title]': 'null' },
  template: `
    <div class="page-header">
      <div class="page-header__text">
        @if (backLink()) {
          <a class="page-header__back" [routerLink]="backLink()">
            <i class="pi pi-arrow-left" aria-hidden="true"></i>
            <span>{{ backLabel() }}</span>
          </a>
        }
        <div class="page-header__title-row">
          <h1 class="page-header__title">{{ title() }}</h1>
          @if (subtitle()) {
            <lpg-info-tip class="page-header__info" [text]="subtitle()" position="bottom" />
          }
        </div>
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
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
        flex-wrap: wrap;
      }

      .page-header__text {
        flex: 1 1 auto;
        min-inline-size: 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
      }

      .page-header__title-row {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        max-inline-size: 100%;
        min-inline-size: 0;
      }

      /* One line each, ellipsis when narrow — never wraps into the header
         search beside it (QA UR-03). */
      .page-header__title {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin: 0;
        font-size: var(--typography-heading1-font-size);
        font-weight: var(--typography-heading1-font-weight);
        line-height: var(--typography-heading1-line-height);
        letter-spacing: -0.01em;
        color: var(--color-text-primary);
      }

      .page-header__info {
        font-size: 0.95rem;
      }

      .page-header__back {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-block-end: 2px;
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        text-decoration: none;
      }

      .page-header__back:hover {
        color: var(--color-action-primary);
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
