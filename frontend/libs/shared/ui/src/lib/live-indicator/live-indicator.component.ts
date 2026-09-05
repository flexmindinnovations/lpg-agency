import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * A small dot that gently pulses to signal live / real-time activity
 * (doc §17, §35 — glow used sparingly). Deliberately tiny: it animates a
 * ring, never a whole card. `active=false` shows a static, muted dot.
 */
@Component({
  selector: 'lpg-live-indicator',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span
      class="live-indicator"
      [class.live-indicator--active]="active()"
      role="status"
      [attr.aria-label]="ariaLabel()"
    >
      <span class="live-indicator__dot"></span>
      @if (label()) {
        <span class="live-indicator__label">{{ label() }}</span>
      }
    </span>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
      }

      .live-indicator {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .live-indicator__dot {
        position: relative;
        inline-size: 8px;
        block-size: 8px;
        border-radius: var(--radius-full);
        background: var(--color-text-disabled);
        flex-shrink: 0;
      }

      .live-indicator--active .live-indicator__dot {
        background: var(--color-status-success);
      }

      .live-indicator--active .live-indicator__dot::after {
        content: '';
        position: absolute;
        inset: -3px;
        border-radius: var(--radius-full);
        background: var(--color-status-success);
        opacity: 0.5;
        animation: lpg-live-pulse 1600ms var(--motion-easing-decelerate) infinite;
      }

      @keyframes lpg-live-pulse {
        0% {
          transform: scale(0.6);
          opacity: 0.55;
        }
        80%,
        100% {
          transform: scale(2.2);
          opacity: 0;
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .live-indicator--active .live-indicator__dot::after {
          animation: none;
          opacity: 0.35;
          transform: scale(1.4);
        }
      }
    `,
  ],
})
export class LiveIndicatorComponent {
  readonly active = input<boolean>(true);
  readonly label = input<string>('');
  readonly ariaLabel = input<string>('Live');
}
