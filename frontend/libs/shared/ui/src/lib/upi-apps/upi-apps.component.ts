import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * The UPI apps a customer can pay from — Google Pay, PhonePe, Paytm and BHIM —
 * as small marks with their names, so a "scan to pay" block reads as the UPI
 * flow people already know. The marks are simplified drawings in each app's
 * brand colours, not the official artwork.
 */
@Component({
  selector: 'lpg-upi-apps',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ul class="upi-apps" aria-label="Works with these UPI apps">
      <li class="upi-apps__item">
        <svg class="upi-apps__mark" viewBox="0 0 40 40" aria-hidden="true">
          <defs>
            <linearGradient id="upi-gpay-g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#4285f4" />
              <stop offset="0.34" stop-color="#ea4335" />
              <stop offset="0.67" stop-color="#fbbc05" />
              <stop offset="1" stop-color="#34a853" />
            </linearGradient>
          </defs>
          <rect width="40" height="40" rx="10" fill="#fff" stroke="#dadce0" />
          <text
            x="20"
            y="28"
            text-anchor="middle"
            font-family="Arial, Helvetica, sans-serif"
            font-size="26"
            font-weight="700"
            fill="url(#upi-gpay-g)"
          >
            G
          </text>
        </svg>
        <span class="upi-apps__name">Google Pay</span>
      </li>
      <li class="upi-apps__item">
        <svg class="upi-apps__mark" viewBox="0 0 40 40" aria-hidden="true">
          <rect width="40" height="40" rx="10" fill="#5f259f" />
          <text
            x="20"
            y="27"
            text-anchor="middle"
            font-family="'Nirmala UI', 'Noto Sans Devanagari', Arial, sans-serif"
            font-size="19"
            font-weight="700"
            fill="#fff"
          >
            पे
          </text>
        </svg>
        <span class="upi-apps__name">PhonePe</span>
      </li>
      <li class="upi-apps__item">
        <svg class="upi-apps__mark" viewBox="0 0 40 40" aria-hidden="true">
          <rect width="40" height="40" rx="10" fill="#fff" stroke="#dadce0" />
          <text
            x="20.5"
            y="25"
            text-anchor="end"
            font-family="Arial, Helvetica, sans-serif"
            font-size="11"
            font-weight="700"
            fill="#002970"
          >
            pay
          </text>
          <text
            x="19.5"
            y="25"
            text-anchor="start"
            font-family="Arial, Helvetica, sans-serif"
            font-size="11"
            font-weight="700"
            fill="#00baf2"
          >
            tm
          </text>
        </svg>
        <span class="upi-apps__name">Paytm</span>
      </li>
      <li class="upi-apps__item">
        <svg class="upi-apps__mark" viewBox="0 0 40 40" aria-hidden="true">
          <rect width="40" height="40" rx="10" fill="#fff" stroke="#dadce0" />
          <path d="M8 31 L16 11 L21 11 L13 31 Z" fill="#f47920" />
          <path d="M19 31 L27 11 L32 11 L24 31 Z" fill="#128807" />
        </svg>
        <span class="upi-apps__name">BHIM</span>
      </li>
    </ul>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .upi-apps {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-md);
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .upi-apps__item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--spacing-xs);
        min-inline-size: 4.5rem;
      }

      .upi-apps__mark {
        inline-size: 2.5rem;
        block-size: 2.5rem;
      }

      .upi-apps__name {
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size, 0.75rem);
      }
    `,
  ],
})
export class UpiAppsComponent {}
