import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { SkeletonComponent } from '../skeleton/skeleton.component';

export type StatTone = 'primary' | 'info' | 'success' | 'warning' | 'danger' | 'neutral';
export type DeltaDirection = 'up' | 'down' | 'flat';

/**
 * A KPI card (doc §15): metric + comparison delta + mini trend sparkline +
 * contextual icon, with a restrained hover (a 1px lift and a border
 * highlight — never a jump). The sparkline is an inline SVG polyline, not a
 * chart library.
 */
@Component({
  selector: 'lpg-stat-card',
  standalone: true,
  imports: [SkeletonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="stat-card">
      <div class="stat-card__head">
        <span class="stat-card__label">{{ label() }}</span>
        @if (icon()) {
          <span class="stat-card__icon stat-card__icon--{{ tone() }}">
            <i class="{{ icon() }}" aria-hidden="true"></i>
          </span>
        }
      </div>

      @if (loading()) {
        <lpg-skeleton width="55%" height="2rem" />
      } @else {
        <div class="stat-card__value">{{ value() }}</div>
      }

      <div class="stat-card__foot">
        @if (delta() && !loading()) {
          <span class="stat-card__delta stat-card__delta--{{ direction() }}">
            <i class="pi {{ deltaIcon() }}" aria-hidden="true"></i>
            {{ delta() }}
          </span>
        }
        @if (caption()) {
          <span class="stat-card__caption">{{ caption() }}</span>
        }
      </div>

      @if (trendPoints().length > 1 && !loading()) {
        <svg
          class="stat-card__spark"
          viewBox="0 0 100 32"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <polyline [attr.points]="sparkPath()" />
        </svg>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .stat-card {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        padding: var(--spacing-lg);
        background: var(--component-card-background);
        border: var(--border-width) solid var(--component-card-border);
        border-radius: var(--radius-card);
        box-shadow: var(--elevation-1);
        transition:
          transform var(--motion-duration-small) var(--motion-easing-emphasized),
          border-color var(--motion-duration-small) var(--motion-easing-emphasized),
          box-shadow var(--motion-duration-small) var(--motion-easing-emphasized);
      }

      .stat-card:hover {
        transform: translateY(-1px);
        border-color: var(--color-border-strong);
        box-shadow: var(--elevation-2);
      }

      .stat-card__head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--spacing-sm);
      }

      .stat-card__label {
        font-size: var(--typography-secondary-font-size);
        color: var(--color-text-secondary);
      }

      .stat-card__icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 2rem;
        block-size: 2rem;
        border-radius: var(--radius-xs);
        font-size: var(--icon-size-md);
        flex-shrink: 0;
      }

      .stat-card__icon--primary {
        background: color-mix(in srgb, var(--color-action-primary) 14%, transparent);
        color: var(--color-action-primary);
      }
      .stat-card__icon--info {
        background: color-mix(in srgb, var(--color-status-info) 14%, transparent);
        color: var(--color-status-info);
      }
      .stat-card__icon--success {
        background: color-mix(in srgb, var(--color-status-success) 14%, transparent);
        color: var(--color-status-success);
      }
      .stat-card__icon--warning {
        background: color-mix(in srgb, var(--color-status-warning) 14%, transparent);
        color: var(--color-status-warning);
      }
      .stat-card__icon--danger {
        background: color-mix(in srgb, var(--color-status-danger) 14%, transparent);
        color: var(--color-status-danger);
      }
      .stat-card__icon--neutral {
        background: var(--color-surface-overlay);
        color: var(--color-text-secondary);
      }

      .stat-card__value {
        font-size: var(--typography-kpi-font-size);
        font-weight: var(--typography-kpi-font-weight);
        line-height: var(--typography-kpi-line-height);
        letter-spacing: -0.02em;
        color: var(--color-text-primary);
      }

      .stat-card__foot {
        display: flex;
        align-items: baseline;
        gap: var(--spacing-sm);
        flex-wrap: wrap;
      }

      .stat-card__delta {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
      }

      .stat-card__delta--up {
        color: var(--color-status-success);
      }
      .stat-card__delta--down {
        color: var(--color-status-danger);
      }
      .stat-card__delta--flat {
        color: var(--color-text-secondary);
      }

      .stat-card__delta i {
        font-size: 10px;
      }

      .stat-card__caption {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .stat-card__spark {
        inline-size: 100%;
        block-size: 2rem;
        margin-block-start: var(--spacing-xs);
        overflow: visible;
      }

      .stat-card__spark polyline {
        fill: none;
        stroke: var(--color-action-primary);
        stroke-width: 1.5;
        stroke-linecap: round;
        stroke-linejoin: round;
        vector-effect: non-scaling-stroke;
      }
    `,
  ],
})
export class StatCardComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string | number>();
  /** PrimeIcon class for the contextual icon. */
  readonly icon = input<string>('');
  readonly tone = input<StatTone>('primary');
  /** Formatted comparison, e.g. "+12.5%". */
  readonly delta = input<string>('');
  /** Overrides the auto-detected direction (from a leading +/- in `delta`). */
  readonly deltaDirection = input<DeltaDirection | null>(null);
  /** e.g. "vs last week". */
  readonly caption = input<string>('');
  /** Values for the mini trend line, oldest → newest. */
  readonly trend = input<readonly number[]>([]);
  readonly loading = input<boolean>(false);

  protected readonly trendPoints = computed(() => this.trend().filter((n) => Number.isFinite(n)));

  protected readonly direction = computed<DeltaDirection>(() => {
    const explicit = this.deltaDirection();
    if (explicit) return explicit;
    const d = this.delta().trim();
    if (d.startsWith('-') || d.startsWith('−')) return 'down';
    if (d.startsWith('+')) return 'up';
    return 'flat';
  });

  protected readonly deltaIcon = computed(() => {
    switch (this.direction()) {
      case 'up':
        return 'pi-arrow-up-right';
      case 'down':
        return 'pi-arrow-down-right';
      default:
        return 'pi-minus';
    }
  });

  protected readonly sparkPath = computed(() => {
    const pts = this.trendPoints();
    if (pts.length < 2) return '';
    const min = Math.min(...pts);
    const max = Math.max(...pts);
    const span = max - min || 1;
    const step = 100 / (pts.length - 1);
    return pts
      .map((v, i) => {
        const x = i * step;
        const y = 30 - ((v - min) / span) * 28 - 1;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(' ');
  });
}
