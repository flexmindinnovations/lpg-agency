import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
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

/**
 * First-time setup checklist on Home (DA-32). Only an admin who can
 * configure the agency (`tenant:configure`) sees it — and only that role
 * calls `/admin/setup-progress`. It disappears once every step is done.
 */
@Component({
  selector: 'lpg-setup-checklist',
  standalone: true,
  imports: [RouterLink, SectionCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (visible()) {
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
    }
  `,
  styles: [
    `
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

  protected readonly steps = STEPS;
  private readonly progress = signal<Readonly<Record<string, boolean>> | null>(null);
  private readonly complete = signal(true);

  protected readonly visible = computed(() => this.progress() !== null && !this.complete());
  protected readonly doneCount = computed(
    () => STEPS.filter((step) => this.progress()?.[step.key]).length,
  );

  constructor() {
    if (!this.authService.principal()?.permissions.has('tenant:configure')) return;
    this.tenantService.getSetupProgress().subscribe({
      next: (response) => {
        this.progress.set(response.steps);
        this.complete.set(response.complete);
      },
      // The checklist is a convenience — Home works without it.
      error: () => this.progress.set(null),
    });
  }

  protected isDone(key: string): boolean {
    return !!this.progress()?.[key];
  }
}
