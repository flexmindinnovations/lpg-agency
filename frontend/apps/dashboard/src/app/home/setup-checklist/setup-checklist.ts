import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  Injectable,
  Injector,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { AdminTenantService, AuthService } from '@lpg/shared/data-access';
import { SectionCardComponent } from '@lpg/shared/ui';

interface SetupStep {
  readonly key: string;
  readonly label: string;
  readonly link: string;
}

/** Same order and keys as the backend's `SETUP_STEPS` (`setup_progress.py`). */
const STEPS: readonly SetupStep[] = [
  { key: 'branch', label: 'Add a branch', link: '/admin/branches' },
  { key: 'warehouse', label: 'Add a godown', link: '/admin/warehouses' },
  { key: 'cylinder_types', label: 'Add cylinder types', link: '/admin/cylinder-types' },
  { key: 'prices', label: 'Set cylinder prices', link: '/admin/price-lists' },
  { key: 'gst', label: 'Set the GST rate', link: '/settings/configuration' },
  { key: 'payments', label: 'Set up payments (UPI or bank)', link: '/settings/payments' },
  { key: 'staff', label: 'Invite your staff', link: '/admin/users' },
  { key: 'drivers', label: 'Add drivers', link: '/drivers' },
  { key: 'vehicles', label: 'Add vehicles', link: '/vehicles' },
];

/** Setup progress already fetched this session, so a revisit shows the card at once. */
@Injectable({ providedIn: 'root' })
class SetupProgressMemory {
  private readonly seen = new Map<string, Readonly<Record<string, boolean>>>();

  get(user: string): Readonly<Record<string, boolean>> | null {
    return this.seen.get(user) ?? null;
  }

  set(user: string, steps: Readonly<Record<string, boolean>>): void {
    this.seen.set(user, steps);
  }
}

/**
 * First-time setup checklist on Home (DA-32). Only an admin who can
 * configure the agency (`tenant:configure`) sees it, and only that role
 * calls `/admin/setup-progress`. It shows only while a step is still to do
 * and disappears once every step is done.
 *
 * The rest of Home does not wait for it. When the answer arrives the card
 * eases in at the top and the cards below move down with it; nothing is held
 * back as empty space meanwhile. A revisit already knows the answer and shows
 * the card straight away.
 */
@Component({
  selector: 'lpg-setup-checklist',
  standalone: true,
  imports: [RouterLink, SectionCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class.setup--shown]': 'visible()',
    '[class.setup--open]': 'open()',
  },
  template: `
    @if (visible()) {
      <div class="setup__inner">
        <lpg-section-card heading="Finish setting up your agency">
          <p class="setup__lede">
            {{ doneCount() }} of {{ steps.length }} done. Orders and invoices need these in place.
          </p>
          <ol class="setup__list">
            @for (step of steps; track step.key) {
              <li class="setup__item" [class.setup__item--done]="isDone(step.key)">
                <i
                  class="pi"
                  [class.pi-check-circle]="isDone(step.key)"
                  [class.pi-circle]="!isDone(step.key)"
                  aria-hidden="true"
                ></i>
                <a [routerLink]="step.link">{{ step.label }}</a>
                <span class="sr-only">{{ isDone(step.key) ? '(done)' : '(to do)' }}</span>
              </li>
            }
          </ol>
        </lpg-section-card>
      </div>
    }
  `,
  styles: [
    `
      /* No card, no box: nothing is reserved while the answer is on its way. */
      :host {
        display: none;
      }

      /* The card opens from nothing. The host is the grid whose one row grows
         from 0 to its content, and its bottom margin cancels the page's gap
         until then (the gap is --spacing-xl on Home), so the cards below slide
         down smoothly instead of jumping. */
      :host(.setup--shown) {
        display: grid;
        grid-template-rows: 0fr;
        margin-block-end: calc(-1 * var(--spacing-xl));
        opacity: 0;
        transform: translateY(calc(-1 * var(--spacing-sm)));
        transition:
          grid-template-rows var(--motion-duration-medium) var(--motion-easing-emphasized),
          margin-block-end var(--motion-duration-medium) var(--motion-easing-emphasized),
          opacity var(--motion-duration-medium) var(--motion-easing-emphasized),
          transform var(--motion-duration-medium) var(--motion-easing-emphasized);
      }

      :host(.setup--open) {
        grid-template-rows: 1fr;
        margin-block-end: 0;
        opacity: 1;
        transform: none;
      }

      @media (prefers-reduced-motion: reduce) {
        :host(.setup--shown) {
          transition: none;
        }
      }

      .setup__inner {
        min-block-size: 0;
        /* Clip while it grows. */
        overflow: clip;
      }

      .setup__lede {
        margin: 0 0 var(--spacing-md);
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }

      .setup__list {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: var(--spacing-sm) var(--spacing-lg);
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .setup__item {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .setup__item a {
        color: var(--color-action-primary);
        text-decoration: none;
        font-weight: var(--typography-label-font-weight);
      }

      .setup__item a:hover {
        text-decoration: underline;
      }

      .setup__item .pi {
        color: var(--color-text-secondary);
      }

      .setup__item--done .pi {
        color: var(--color-status-success);
      }

      .setup__item--done a {
        color: var(--color-text-secondary);
        text-decoration: line-through;
      }

      .sr-only {
        position: absolute;
        inline-size: 1px;
        block-size: 1px;
        overflow: hidden;
        clip-path: inset(50%);
        white-space: nowrap;
      }
    `,
  ],
})
export class SetupChecklist {
  private readonly tenantService = inject(AdminTenantService);
  private readonly authService = inject(AuthService);
  private readonly memory = inject(SetupProgressMemory);
  private readonly injector = inject(Injector);

  protected readonly steps = STEPS;
  private readonly progress = signal<Readonly<Record<string, boolean>> | null>(null);
  /** True once the card has been drawn closed and may grow open. */
  protected readonly open = signal(false);

  /** Shown only while at least one step is still to do. */
  protected readonly visible = computed(() => {
    const progress = this.progress();
    return progress !== null && STEPS.some((step) => !progress[step.key]);
  });
  protected readonly doneCount = computed(
    () => STEPS.filter((step) => this.progress()?.[step.key]).length,
  );

  constructor() {
    const principal = this.authService.principal();
    if (!principal?.permissions.has('tenant:configure')) return;
    const user = principal.userId;

    const known = this.memory.get(user);
    if (known) {
      // Seen this session: show the card as it was, no entrance, then refresh.
      this.progress.set(known);
      this.open.set(true);
    }

    effect(() => {
      if (!this.visible() || this.open()) return;
      // Let the closed card paint once, then open it so the move is animated.
      afterNextRender(() => requestAnimationFrame(() => this.open.set(true)), {
        injector: this.injector,
      });
    });

    this.tenantService.getSetupProgress().subscribe({
      next: (response) => {
        this.memory.set(user, response.steps);
        this.progress.set(response.steps);
      },
      // The checklist is a convenience — Home works without it.
      error: () => this.progress.set(null),
    });
  }

  protected isDone(key: string): boolean {
    return !!this.progress()?.[key];
  }
}
