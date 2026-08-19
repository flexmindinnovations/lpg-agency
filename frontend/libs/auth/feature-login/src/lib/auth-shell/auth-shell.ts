import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Shared split-panel frame for the auth flow (login, forgot/reset password).
 * Left panel is a fixed brand navy regardless of the app's light/dark theme
 * (an intentional constant, matching the same split-screen convention as
 * Stripe/Linear-style auth screens) — the right panel hosts the projected
 * form and stays fully theme-reactive via the normal design tokens.
 */
@Component({
  selector: 'lpg-auth-shell',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="auth-shell">
      <aside class="auth-shell__brand" aria-hidden="true">
        <div class="auth-shell__brand-glow"></div>
        <div class="auth-shell__brand-content">
          <div class="auth-shell__brand-mark-row">
            <svg class="auth-shell__brand-mark" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M12 2C15 5 19 9 19 14.5C19 18.64 15.86 22 12 22C8.14 22 5 18.64 5 14.5C5 9 9 5 12 2Z"
                fill="currentColor"
              />
              <path
                d="M12 10C13.5 12 15 13.5 15 15.5C15 17.43 13.66 19 12 19C10.34 19 9 17.43 9 15.5C9 13.5 10.5 12 12 10Z"
                fill="var(--primitive-color-flame-orange-500, #ff6f12)"
              />
            </svg>
            <span class="auth-shell__brand-name">LPG Agency</span>
          </div>
          <p class="auth-shell__brand-tagline">
            Bookings, deliveries, and billing for your LPG distribution business, all in one
            place.
          </p>
        </div>
      </aside>

      <main class="auth-shell__content">
        <div class="auth-shell__content-inner">
          <div class="auth-shell__mobile-brand">
            <svg class="auth-shell__mobile-brand-mark" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M12 2C15 5 19 9 19 14.5C19 18.64 15.86 22 12 22C8.14 22 5 18.64 5 14.5C5 9 9 5 12 2Z"
                fill="currentColor"
              />
              <path
                d="M12 10C13.5 12 15 13.5 15 15.5C15 17.43 13.66 19 12 19C10.34 19 9 17.43 9 15.5C9 13.5 10.5 12 12 10Z"
                fill="var(--primitive-color-flame-orange-500, #ff6f12)"
              />
            </svg>
            <span>LPG Agency</span>
          </div>
          <ng-content />
        </div>
      </main>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        min-block-size: 100vh;
      }

      .auth-shell {
        display: block;
        min-block-size: 100vh;
      }

      /* ---- Brand panel (left, desktop only) ---- */

      .auth-shell__brand {
        position: relative;
        display: none;
        flex-direction: column;
        justify-content: flex-end;
        overflow: hidden;
        padding: var(--spacing-2xl);
        background: linear-gradient(
          160deg,
          var(--primitive-color-gas-blue-900) 0%,
          var(--primitive-color-gas-blue-800) 60%,
          var(--primitive-color-gas-blue-700) 100%
        );
        color: var(--primitive-color-gray-50);
      }

      .auth-shell__brand-glow {
        position: absolute;
        inset-block-end: -18%;
        inset-inline-start: -12%;
        inline-size: 32rem;
        block-size: 32rem;
        border-radius: var(--radius-full);
        background: radial-gradient(
          circle,
          var(--primitive-color-flame-orange-500) 0%,
          transparent 70%
        );
        opacity: 0.18;
        pointer-events: none;
      }

      .auth-shell__brand-content {
        position: relative;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        max-inline-size: 26rem;
      }

      .auth-shell__brand-mark-row {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .auth-shell__brand-mark {
        inline-size: 2rem;
        block-size: 2rem;
        flex-shrink: 0;
        color: var(--primitive-color-gray-50);
      }

      .auth-shell__brand-name {
        font-size: var(--typography-heading2-font-size);
        font-weight: var(--typography-heading1-font-weight);
        letter-spacing: -0.02em;
      }

      .auth-shell__brand-tagline {
        margin: 0;
        font-size: var(--typography-body-font-size);
        line-height: var(--typography-body-line-height);
        color: var(--primitive-color-gas-blue-100);
      }

      /* ---- Content panel (right, always visible) ---- */

      .auth-shell__content {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: var(--spacing-lg);
        background: var(--color-surface-base);
      }

      .auth-shell__content-inner {
        inline-size: 100%;
        max-inline-size: 23rem;
        animation: auth-shell-enter var(--motion-duration-large) var(--motion-easing-decelerate);
      }

      .auth-shell__mobile-brand {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--spacing-sm);
        margin-block-end: var(--spacing-xl);
        font-size: var(--typography-heading2-font-size);
        font-weight: var(--typography-heading1-font-weight);
        letter-spacing: -0.02em;
        color: var(--color-text-primary);
      }

      .auth-shell__mobile-brand-mark {
        inline-size: 1.75rem;
        block-size: 1.75rem;
        color: var(--color-action-primary);
      }

      @keyframes auth-shell-enter {
        from {
          opacity: 0;
          transform: translateY(8px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .auth-shell__content-inner {
          animation: none;
        }
      }

      @media (min-width: 900px) {
        .auth-shell {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        }

        .auth-shell__brand {
          display: flex;
        }

        .auth-shell__mobile-brand {
          display: none;
        }

        .auth-shell__content {
          padding: var(--spacing-2xl);
        }
      }
    `,
  ],
})
export class AuthShell {}
