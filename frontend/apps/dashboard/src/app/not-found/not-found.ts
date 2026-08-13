import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'lpg-not-found',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="not-found">
      <div class="not-found__content">
        <span class="not-found__code">404</span>
        <h1 class="not-found__title">Page not found</h1>
        <p class="not-found__desc">The page you're looking for doesn't exist or has been moved.</p>
        <a routerLink="/" class="not-found__link">
          <i class="pi pi-arrow-left" aria-hidden="true"></i>
          Back to home
        </a>
      </div>
    </div>
  `,
  styles: [
    `
      .not-found {
        display: flex;
        align-items: center;
        justify-content: center;
        block-size: calc(100vh - 120px);
      }

      .not-found__content {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: var(--spacing-sm);
      }

      .not-found__code {
        font-size: 4rem;
        font-weight: 700;
        letter-spacing: -0.04em;
        color: var(--color-border-default);
        line-height: 1;
      }

      .not-found__title {
        font-size: var(--typography-heading1-font-size);
        font-weight: var(--typography-heading1-font-weight);
        letter-spacing: -0.025em;
        margin: 0;
      }

      .not-found__desc {
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
        margin: 0;
        max-inline-size: 32ch;
      }

      .not-found__link {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        margin-block-start: var(--spacing-md);
        color: var(--color-action-primary);
        text-decoration: none;
        font-size: var(--typography-body-small-font-size);
        font-weight: var(--typography-label-font-weight);
      }

      .not-found__link:hover {
        text-decoration: underline;
      }
    `,
  ],
})
export class NotFound {}
