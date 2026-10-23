import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { Tooltip } from 'primeng/tooltip';

/**
 * The title block for a page — heading, info-circle tooltip for subtitle, optional
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
  imports: [RouterLink, Tooltip],
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
        <div class="page-header__title-row">
          <h1 class="page-header__title">{{ title() }}</h1>
          @if (subtitle()) {
            <button
              type="button"
              class="page-header__info"
              [pTooltip]="subtitle()"
              tooltipPosition="bottom"
              [attr.aria-label]="subtitle()"
              [attr.aria-expanded]="isInfoOpen()"
              (click)="toggleInfo($event)"
            >
              <i class="pi pi-info-circle" aria-hidden="true"></i>
            </button>
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
        background: transparent;
        border: none;
        font-family: inherit;
        font-size: 0.95rem;
        color: var(--color-text-secondary);
        cursor: pointer;
        flex-shrink: 0;
        transition: color var(--motion-duration-fast) var(--motion-easing-standard);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 2px;
        margin: 0;
        border-radius: var(--radius-sm);
        line-height: 1;
      }

      .page-header__info:hover,
      .page-header__info:focus-visible {
        color: var(--color-action-primary);
        outline: none;
      }

      .page-header__info:focus-visible {
        box-shadow: 0 0 0 2px var(--color-action-primary);
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

  protected readonly isInfoOpen = signal(false);
  private readonly infoTooltip = viewChild(Tooltip);

  protected toggleInfo(event: Event): void {
    event.stopPropagation();
    const tip = this.infoTooltip();
    if (this.isInfoOpen() || tip?.active) {
      tip?.deactivate();
      this.isInfoOpen.set(false);
    } else {
      tip?.activate();
      this.isInfoOpen.set(true);
    }
  }

  @HostListener('document:click')
  onDocumentClick(): void {
    if (this.isInfoOpen()) {
      this.infoTooltip()?.deactivate();
      this.isInfoOpen.set(false);
    }
  }
}
