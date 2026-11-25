import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ToggleSwitch } from 'primeng/toggleswitch';
import {
  AgencyService,
  NotifyService,
  errorMessageFor,
  type ModuleResponse,
} from '@lpg/shared/data-access';

/**
 * Switches an agency's optional modules on or off (Platform Console, super
 * admin). Every module is on until switched off. A module that is off is
 * hidden from the agency's dashboard and its API refuses calls.
 */
@Component({
  selector: 'lpg-agency-modules',
  standalone: true,
  imports: [FormsModule, ToggleSwitch],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="modules" aria-labelledby="agency-modules-heading">
      <h3 id="agency-modules-heading" class="modules__heading">
        Modules
        @if (!loading() && !failed()) {
          <span>· {{ enabledCount() }} of {{ modules().length }} on</span>
        }
      </h3>
      <p class="modules__hint">Switched-off modules are hidden from this agency and blocked.</p>

      @if (loading()) {
        <p class="modules__hint">Loading modules…</p>
      } @else if (failed()) {
        <p class="modules__hint">Modules could not be loaded.</p>
      } @else {
        <ul class="modules__list">
          @for (module of modules(); track module.key) {
            <li class="modules__item">
              <div class="modules__text">
                <span class="modules__label">{{ module.label }}</span>
                <span class="modules__hint">{{ module.description }}</span>
              </div>
              <p-toggleswitch
                [ngModel]="module.enabled"
                [disabled]="readonly() || busy() === module.key"
                [ariaLabel]="module.label"
                (onChange)="toggle(module, $event.checked)"
              />
            </li>
          }
        </ul>
      }
    </section>
  `,
  styles: [
    `
      .modules {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        margin-block: var(--spacing-lg);
      }

      .modules__heading {
        margin: 0;
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
      }

      .modules__list {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .modules__item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
      }

      .modules__text {
        display: flex;
        flex-direction: column;
        min-inline-size: 0;
      }

      .modules__label {
        color: var(--color-text-primary);
        font-weight: var(--typography-label-font-weight);
      }

      .modules__hint {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }
    `,
  ],
})
export class AgencyModules implements OnInit {
  private readonly agencyService = inject(AgencyService);
  private readonly notify = inject(NotifyService);

  readonly tenantId = input.required<string>();
  /** A closed agency's modules are shown but not editable. */
  readonly readonly = input(false);

  protected readonly modules = signal<ModuleResponse[]>([]);
  protected readonly enabledCount = computed(() => this.modules().filter((m) => m.enabled).length);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  protected readonly busy = signal<string | null>(null);

  ngOnInit(): void {
    this.agencyService.listModules(this.tenantId()).subscribe({
      next: (modules) => {
        this.modules.set(modules);
        this.loading.set(false);
      },
      error: () => {
        this.failed.set(true);
        this.loading.set(false);
      },
    });
  }

  protected toggle(module: ModuleResponse, enabled: boolean): void {
    this.busy.set(module.key);
    // Show the new state at once; put it back if the server refuses.
    this.setEnabled(module.key, enabled);
    this.agencyService.setModuleEnabled(this.tenantId(), module.key, enabled).subscribe({
      next: () => this.busy.set(null),
      error: (err) => {
        this.setEnabled(module.key, !enabled);
        this.busy.set(null);
        this.notify.error(errorMessageFor(err));
      },
    });
  }

  private setEnabled(moduleKey: string, enabled: boolean): void {
    this.modules.update((list) => list.map((m) => (m.key === moduleKey ? { ...m, enabled } : m)));
  }
}
