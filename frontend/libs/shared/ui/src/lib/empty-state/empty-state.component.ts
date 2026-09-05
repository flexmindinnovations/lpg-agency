import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type EmptyStateTone = 'neutral' | 'error';

/**
 * Calm, informative empty / error state (doc §36, §37).
 *
 * `tone="error"` is the same layout with a danger-coloured icon — an error
 * should still say *what happened / why / what the user can do*, so the
 * consumer supplies the description and a Retry control via the `actions`
 * slot rather than this component inventing copy.
 */
@Component({
  selector: 'lpg-empty-state',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="empty-state" [class.empty-state--error]="tone() === 'error'" role="status">
      <i class="empty-state__icon {{ resolvedIcon() }}" aria-hidden="true"></i>
      <p class="empty-state__title">{{ title() }}</p>
      @if (description()) {
        <p class="empty-state__description">{{ description() }}</p>
      }
      <div class="empty-state__actions">
        <ng-content select="[actions]" />
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: var(--spacing-xs);
        padding: var(--spacing-2xl) var(--spacing-lg);
        animation: lpg-empty-in var(--motion-duration-small) var(--motion-easing-emphasized) both;
      }

      .empty-state__icon {
        font-size: var(--icon-size-xl);
        color: var(--color-text-secondary);
        margin-block-end: var(--spacing-xs);
      }

      .empty-state--error .empty-state__icon {
        color: var(--color-status-danger);
      }

      .empty-state__title {
        margin: 0;
        font-size: var(--typography-heading3-font-size);
        font-weight: var(--typography-heading3-font-weight);
        color: var(--color-text-primary);
      }

      .empty-state__description {
        margin: 0;
        max-inline-size: 40ch;
        font-size: var(--typography-secondary-font-size);
        color: var(--color-text-secondary);
      }

      .empty-state__actions {
        margin-block-start: var(--spacing-md);
        display: flex;
        gap: var(--spacing-sm);
      }

      .empty-state__actions:empty {
        display: none;
      }

      @keyframes lpg-empty-in {
        from {
          opacity: 0;
          transform: translateY(4px);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .empty-state {
          animation: none;
        }
      }
    `,
  ],
})
export class EmptyStateComponent {
  readonly title = input.required<string>();
  readonly description = input<string>('');
  readonly tone = input<EmptyStateTone>('neutral');
  /** PrimeIcon class. Defaults by tone when not given. */
  readonly icon = input<string>('');

  protected readonly resolvedIcon = computed(
    () => this.icon() || (this.tone() === 'error' ? 'pi pi-exclamation-triangle' : 'pi pi-inbox'),
  );
}
