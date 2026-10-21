import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

interface DeadEndCopy {
  readonly code: string;
  readonly title: string;
  readonly description: string;
}

const NOT_FOUND: DeadEndCopy = {
  code: '404',
  title: 'Page not found',
  description: "The page you're looking for doesn't exist or has been moved.",
};

/** Shown by `permissionGuard` (route `data.variant: 'no-access'`) — DO-31. */
const NO_ACCESS: DeadEndCopy = {
  code: '403',
  title: "You don't have access to this page",
  description: 'Your role does not include this area. Ask your agency admin if you need it.',
};

@Component({
  selector: 'lpg-not-found',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="not-found">
      <div class="not-found__content">
        <span class="not-found__code" aria-hidden="true">{{ copy.code }}</span>
        <h1 class="not-found__title">{{ copy.title }}</h1>
        <p class="not-found__desc">{{ copy.description }}</p>
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
export class NotFound {
  protected readonly copy =
    inject(ActivatedRoute).snapshot.data['variant'] === 'no-access' ? NO_ACCESS : NOT_FOUND;
}
