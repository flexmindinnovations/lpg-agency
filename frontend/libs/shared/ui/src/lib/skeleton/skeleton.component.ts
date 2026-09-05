import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type SkeletonVariant = 'block' | 'text' | 'circle' | 'table';

/**
 * Loading-state placeholder with a subtle luminance shimmer (doc §24).
 *
 * One parametric component rather than the three the plan sketched
 * (`SkeletonBlock`/`List`/`Table`) — the shapes only differ by how many
 * bars and in what grid, which a `variant` input expresses without three
 * near-identical files.
 *
 * The shimmer animation is defined here (component-scoped) so a story
 * renders it correctly without depending on the dashboard app's global
 * stylesheet; it is disabled under `prefers-reduced-motion`.
 */
@Component({
  selector: 'lpg-skeleton',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @switch (variant()) {
      @case ('table') {
        <div class="skeleton-table" [attr.aria-hidden]="true">
          <div class="skeleton-table__row skeleton-table__row--head">
            @for (c of cols(); track $index) {
              <span class="skeleton-bar"></span>
            }
          </div>
          @for (r of rowList(); track $index) {
            <div class="skeleton-table__row">
              @for (c of cols(); track $index) {
                <span class="skeleton-bar"></span>
              }
            </div>
          }
        </div>
      }
      @case ('text') {
        <div class="skeleton-text" [attr.aria-hidden]="true">
          @for (l of lineList(); track $index) {
            <span
              class="skeleton-bar"
              [style.inline-size]="$last ? '60%' : '100%'"
            ></span>
          }
        </div>
      }
      @default {
        <span
          class="skeleton-bar"
          [class.skeleton-bar--circle]="variant() === 'circle'"
          [style.inline-size]="width()"
          [style.block-size]="height()"
          [attr.aria-hidden]="true"
        ></span>
      }
    }
    <span class="skeleton-sr">Loading…</span>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .skeleton-bar {
        display: block;
        inline-size: 100%;
        block-size: 1rem;
        border-radius: var(--radius-xs);
        background: linear-gradient(
          90deg,
          var(--color-surface-overlay) 25%,
          color-mix(in srgb, var(--color-surface-overlay), var(--color-text-primary) 8%) 37%,
          var(--color-surface-overlay) 63%
        );
        background-size: 400% 100%;
        animation: lpg-skeleton-shimmer var(--motion-duration-large) linear infinite;
      }

      .skeleton-bar--circle {
        border-radius: var(--radius-full);
      }

      .skeleton-text {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
      }

      .skeleton-table {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
      }

      .skeleton-table__row {
        display: flex;
        gap: var(--spacing-md);
      }

      .skeleton-table__row .skeleton-bar {
        flex: 1;
      }

      .skeleton-table__row--head .skeleton-bar {
        block-size: 0.75rem;
        opacity: 0.7;
      }

      /* Visually hidden, announced by AT so a loading region isn't silent. */
      .skeleton-sr {
        position: absolute;
        inline-size: 1px;
        block-size: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      @keyframes lpg-skeleton-shimmer {
        0% {
          background-position: 100% 50%;
        }
        100% {
          background-position: 0 50%;
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .skeleton-bar {
          animation: none;
          background: var(--color-surface-overlay);
        }
      }
    `,
  ],
})
export class SkeletonComponent {
  readonly variant = input<SkeletonVariant>('block');
  /** `block`/`circle` only. Any CSS length. */
  readonly width = input<string>('100%');
  readonly height = input<string>('1rem');
  /** `text` variant — number of lines. */
  readonly lines = input<number>(3);
  /** `table` variant — body row count. */
  readonly rows = input<number>(6);
  /** `table` variant — column count. */
  readonly columns = input<number>(4);

  protected readonly lineList = computed(() => Array.from({ length: Math.max(1, this.lines()) }));
  protected readonly rowList = computed(() => Array.from({ length: Math.max(1, this.rows()) }));
  protected readonly cols = computed(() => Array.from({ length: Math.max(1, this.columns()) }));
}
