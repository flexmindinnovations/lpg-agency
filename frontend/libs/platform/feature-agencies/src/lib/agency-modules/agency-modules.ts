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
import { Observable, catchError, finalize, map, of } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { ToggleSwitch } from 'primeng/toggleswitch';
import {
  AgencyService,
  NotifyService,
  errorMessageFor,
  type ModuleResponse,
} from '@lpg/shared/data-access';

/**
 * Switches an agency's modules on or off (Platform Console, super admin).
 * Every module is off until switched on; a module that is off is hidden from
 * the agency's dashboard and its API refuses calls. A module can only be on
 * while the modules it needs are on, so the switches follow that order.
 */
@Component({
  selector: 'lpg-agency-modules',
  standalone: true,
  imports: [FormsModule, ToggleSwitch, ButtonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="modules" aria-labelledby="agency-modules-heading">
      <div class="modules__header">
        <h3 id="agency-modules-heading" class="modules__heading">
          Modules
          @if (!loading() && !failed()) {
            <span>· {{ enabledCount() }} of {{ modules().length }} on</span>
          }
        </h3>
        @if (!loading() && !failed() && !readonly()) {
          <div class="modules__bulk">
            <button
              pButton
              type="button"
              size="small"
              severity="secondary"
              [disabled]="busy() !== null || enabledCount() === modules().length"
              (click)="setAll(true)"
            >
              <span>Turn all on</span>
            </button>
            <button
              pButton
              type="button"
              size="small"
              severity="secondary"
              [disabled]="busy() !== null || enabledCount() === 0"
              (click)="setAll(false)"
            >
              <span>Turn all off</span>
            </button>
          </div>
        }
      </div>
      <p class="modules__hint">
        New agencies start with every module off. Home, Notifications, Settings and the
        Administration screens are always available.
      </p>

      @if (loading()) {
        <p class="modules__hint">Loading modules…</p>
      } @else if (failed()) {
        <p class="modules__hint">Modules could not be loaded.</p>
      } @else {
        @for (group of groups(); track group.name) {
          <h4 class="modules__group">{{ group.name }}</h4>
          <ul class="modules__list">
            @for (module of group.modules; track module.key) {
              <li class="modules__item">
                <div class="modules__text">
                  <span class="modules__label">{{ module.label }}</span>
                  <span class="modules__hint">{{ module.description }}</span>
                  @if (hint(module); as note) {
                    <span class="modules__hint modules__hint--note">{{ note }}</span>
                  }
                </div>
                <p-toggleswitch
                  [ngModel]="module.enabled"
                  [disabled]="readonly() || busy() !== null || locked(module)"
                  [ariaLabel]="module.label"
                  (onChange)="toggle(module, $event.checked)"
                />
              </li>
            }
          </ul>
        }
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

      .modules__header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
        flex-wrap: wrap;
      }

      .modules__bulk {
        display: flex;
        gap: var(--spacing-xs);
      }

      .modules__group {
        margin: var(--spacing-sm) 0 0;
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .modules__hint--note {
        color: var(--color-text-primary);
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
  /** Set while any switch is being saved, so changes happen one at a time, in order. */
  protected readonly busy = signal<string | null>(null);

  protected readonly groups = computed(() => {
    const groups = new Map<string, ModuleResponse[]>();
    for (const module of this.modules()) {
      groups.set(module.group, [...(groups.get(module.group) ?? []), module]);
    }
    return [...groups].map(([name, modules]) => ({ name, modules }));
  });

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

  /** Modules this one needs that are still off. */
  private missing(module: ModuleResponse): ModuleResponse[] {
    return this.modules().filter((m) => module.requires.includes(m.key) && !m.enabled);
  }

  /** Modules that are on and need this one. */
  private dependents(module: ModuleResponse): ModuleResponse[] {
    return this.modules().filter((m) => m.enabled && m.requires.includes(module.key));
  }

  /** A switch is locked while turning it that way would break a dependency. */
  protected locked(module: ModuleResponse): boolean {
    return module.enabled ? this.dependents(module).length > 0 : this.missing(module).length > 0;
  }

  protected hint(module: ModuleResponse): string {
    if (module.enabled) {
      const names = this.dependents(module).map((m) => m.label);
      return names.length ? `Needed by ${names.join(', ')}. Turn those off first.` : '';
    }
    const names = this.missing(module).map((m) => m.label);
    return names.length ? `Needs ${names.join(', ')}. Turn those on first.` : '';
  }

  protected toggle(module: ModuleResponse, enabled: boolean): void {
    this.save(module, enabled).subscribe();
  }

  /** Turns every module on (needed ones first) or off (dependents first), one by one. */
  protected setAll(enabled: boolean): void {
    const order = enabled ? this.modules() : [...this.modules()].reverse();
    const targets = order.filter((m) => m.enabled !== enabled);
    const step = (index: number): void => {
      if (index >= targets.length) {
        return;
      }
      this.save(targets[index], enabled).subscribe((ok) => ok && step(index + 1));
    };
    step(0);
  }

  /** Saves one switch. Emits whether the server accepted it; a refusal is put back and shown. */
  private save(module: ModuleResponse, enabled: boolean): Observable<boolean> {
    this.busy.set(module.key);
    // Show the new state at once; put it back if the server refuses.
    this.setEnabled(module.key, enabled);
    return this.agencyService.setModuleEnabled(this.tenantId(), module.key, enabled).pipe(
      map(() => true),
      catchError((err) => {
        this.setEnabled(module.key, !enabled);
        this.notify.error(errorMessageFor(err));
        return of(false);
      }),
      finalize(() => this.busy.set(null)),
    );
  }

  private setEnabled(moduleKey: string, enabled: boolean): void {
    this.modules.update((list) => list.map((m) => (m.key === moduleKey ? { ...m, enabled } : m)));
  }
}
