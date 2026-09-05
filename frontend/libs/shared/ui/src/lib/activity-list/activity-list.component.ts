import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export type ActivityStatusTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

export interface ActivityItem {
  /** Pre-formatted time, e.g. "09:42" or "2m ago". */
  readonly time: string;
  /** PrimeIcon class. */
  readonly icon: string;
  readonly title: string;
  readonly description?: string;
  readonly status?: string;
  readonly statusTone?: ActivityStatusTone;
}

/**
 * The "Recent Activity" row list (doc §17): time · icon · description ·
 * status. A read-only projection of an already-fetched list — no
 * interaction, no per-row animation.
 */
@Component({
  selector: 'lpg-activity-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ul class="activity-list">
      @for (item of items(); track $index) {
        <li class="activity-list__item">
          <span class="activity-list__icon">
            <i class="{{ item.icon }}" aria-hidden="true"></i>
          </span>
          <div class="activity-list__body">
            <p class="activity-list__title">{{ item.title }}</p>
            @if (item.description) {
              <p class="activity-list__desc">{{ item.description }}</p>
            }
          </div>
          <div class="activity-list__meta">
            @if (item.status) {
              <span class="activity-list__status activity-list__status--{{ item.statusTone ?? 'neutral' }}">
                {{ item.status }}
              </span>
            }
            <time class="activity-list__time">{{ item.time }}</time>
          </div>
        </li>
      }
    </ul>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .activity-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
      }

      .activity-list__item {
        display: flex;
        align-items: flex-start;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) 0;
        border-block-end: var(--border-width) solid var(--color-border-default);
      }

      .activity-list__item:last-child {
        border-block-end: none;
      }

      .activity-list__icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 1.75rem;
        block-size: 1.75rem;
        border-radius: var(--radius-xs);
        background: var(--color-surface-overlay);
        color: var(--color-text-secondary);
        font-size: var(--icon-size-sm);
        flex-shrink: 0;
      }

      .activity-list__body {
        flex: 1;
        min-inline-size: 0;
      }

      .activity-list__title {
        margin: 0;
        font-size: var(--typography-secondary-font-size);
        color: var(--color-text-primary);
      }

      .activity-list__desc {
        margin: 2px 0 0;
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .activity-list__meta {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        flex-shrink: 0;
      }

      .activity-list__time {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        white-space: nowrap;
      }

      .activity-list__status {
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        padding: 1px 6px;
        border-radius: var(--radius-xs);
      }

      .activity-list__status--neutral {
        background: var(--color-surface-overlay);
        color: var(--color-text-secondary);
      }
      .activity-list__status--success {
        background: color-mix(in srgb, var(--color-status-success) 16%, transparent);
        color: var(--color-status-success);
      }
      .activity-list__status--warning {
        background: color-mix(in srgb, var(--color-status-warning) 16%, transparent);
        color: var(--color-status-warning);
      }
      .activity-list__status--danger {
        background: color-mix(in srgb, var(--color-status-danger) 16%, transparent);
        color: var(--color-status-danger);
      }
      .activity-list__status--info {
        background: color-mix(in srgb, var(--color-status-info) 16%, transparent);
        color: var(--color-status-info);
      }
    `,
  ],
})
export class ActivityListComponent {
  readonly items = input.required<readonly ActivityItem[]>();
}
