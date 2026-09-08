import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type StarRatingSize = 'sm' | 'md' | 'lg';

/**
 * Read-only 1–5 star display (TDT quarterly rating; Phase 20 subsystem 2).
 * `stars` is `null` for "not yet rated" (no config or no delivered orders
 * in the period) — rendered as a dash, never a guessed/zero rating.
 *
 * Same tiny-atom shape as `SkeletonComponent`/`EmptyStateComponent`: pure
 * display, OnPush, token-themed, PrimeIcons `pi-star-fill`/`pi-star`.
 */
@Component({
  selector: 'lpg-star-rating',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (stars() === null) {
      <span class="star-rating star-rating--empty" role="img" [attr.aria-label]="emptyLabel()">
        <span class="star-rating__dash" aria-hidden="true">—</span>
      </span>
    } @else {
      <span
        class="star-rating star-rating--{{ size() }}"
        role="img"
        [attr.aria-label]="filledLabel()"
      >
        @for (i of starIndexes(); track i) {
          <i
            class="pi star-rating__star"
            [class.pi-star-fill]="i <= (stars() ?? 0)"
            [class.pi-star]="i > (stars() ?? 0)"
            [class.star-rating__star--filled]="i <= (stars() ?? 0)"
            aria-hidden="true"
          ></i>
        }
      </span>
    }
  `,
  styles: [
    `
      :host {
        display: inline-block;
      }

      .star-rating {
        display: inline-flex;
        align-items: center;
        gap: 2px;
      }

      .star-rating__star {
        color: var(--color-border-strong);
        font-size: var(--icon-size-md);
      }

      .star-rating__star--filled {
        color: var(--color-status-warning);
      }

      .star-rating--sm .star-rating__star {
        font-size: var(--icon-size-sm);
      }

      .star-rating--lg .star-rating__star {
        font-size: var(--icon-size-lg);
      }

      .star-rating--empty {
        color: var(--color-text-secondary);
      }

      .star-rating__dash {
        font-size: var(--typography-secondary-font-size);
      }
    `,
  ],
})
export class StarRatingComponent {
  /** `null` = not yet rated. */
  readonly stars = input<number | null>(null);
  readonly max = input<number>(5);
  readonly size = input<StarRatingSize>('md');

  protected readonly starIndexes = computed(() =>
    Array.from({ length: Math.max(1, this.max()) }, (_, i) => i + 1),
  );

  protected readonly emptyLabel = computed(() => 'Not yet rated');

  protected readonly filledLabel = computed(() => `${this.stars()} out of ${this.max()} stars`);
}
