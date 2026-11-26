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
import { DialogModule } from 'primeng/dialog';
import { ToggleSwitch } from 'primeng/toggleswitch';
import {
  AgencyService,
  NotifyService,
  errorMessageFor,
  type ModuleResponse,
} from '@lpg/shared/data-access';

/**
 * An agency's modules (Platform Console, super admin): a one-line summary with
 * a button that opens every switch in a dialog. Every module is off until
 * switched on; a module that is off is hidden from the agency's dashboard and
 * its API refuses calls. A module can only be on while the modules it needs
 * are on, so the switches follow that order.
 */
@Component({
  selector: 'lpg-agency-modules',
  standalone: true,
  imports: [FormsModule, ToggleSwitch, ButtonModule, DialogModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="summary" aria-labelledby="agency-modules-heading">
      <div class="summary__text">
        <h3 id="agency-modules-heading" class="summary__heading">Modules</h3>
        <span class="summary__status" aria-live="polite">
          @if (loading()) {
            Loading modules…
          } @else if (failed()) {
            Modules could not be loaded.
          } @else {
            {{ enabledCount() }} of {{ modules().length }} on
          }
        </span>
      </div>
      <button
        #openButton
        pButton
        type="button"
        size="small"
        severity="secondary"
        class="summary__open"
        [disabled]="loading() || failed()"
        (click)="dialogOpen.set(true)"
      >
        <i class="pi pi-th-large" aria-hidden="true"></i>
        <span>{{ readonly() ? 'View modules' : 'Manage modules' }}</span>
      </button>
    </section>

    <p-dialog
      [visible]="dialogOpen()"
      (visibleChange)="dialogOpen.set($event)"
      (onHide)="openButton.focus()"
      [header]="'Modules · ' + agencyName()"
      [modal]="true"
      [closeOnEscape]="true"
      [draggable]="false"
      [resizable]="false"
      appendTo="body"
      [style]="{ width: '56rem', maxWidth: '95vw' }"
    >
      <div class="toolbar">
        <p class="hint toolbar__hint">
          Switched-off modules are hidden from this agency and blocked. Home, Notifications,
          Settings and the Administration screens are always available. Changes save as you make
          them.
        </p>
        @if (!readonly()) {
          <div class="toolbar__bulk">
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

      @for (group of groups(); track group.name) {
        <h4 class="group">{{ group.name }}</h4>
        <ul class="grid">
          @for (module of group.modules; track module.key) {
            <li class="module">
              <div class="module__text">
                <span class="module__label">{{ module.label }}</span>
                <span class="hint">{{ module.description }}</span>
                @if (hint(module); as note) {
                  <span class="hint module__note">{{ note }}</span>
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

      <ng-template #footer>
        <div class="footer">
          <span class="hint" aria-live="polite">
            {{ enabledCount() }} of {{ modules().length }} on
          </span>
          <button pButton type="button" (click)="dialogOpen.set(false)">Done</button>
        </div>
      </ng-template>
    </p-dialog>
  `,
  styles: [
    `
      .summary {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: var(--spacing-md);
      }

      .summary__text {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .summary__heading {
        margin: 0;
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .summary__status {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-primary);
      }

      .toolbar {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: var(--spacing-md);
        padding-block-start: var(--spacing-md);
      }

      .toolbar__hint {
        flex: 1 1 20rem;
      }

      .toolbar__bulk {
        display: flex;
        gap: var(--spacing-sm);
      }

      .group {
        margin: var(--spacing-lg) 0 var(--spacing-sm);
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
        gap: var(--spacing-sm);
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .module {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-md);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-input);
      }

      .module__text {
        display: flex;
        flex-direction: column;
        min-inline-size: 0;
      }

      .module__label {
        color: var(--color-text-primary);
        font-weight: var(--typography-label-font-weight);
      }

      .module__note {
        color: var(--color-text-primary);
      }

      .hint {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }

      .footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
        inline-size: 100%;
      }
    `,
  ],
})
export class AgencyModules implements OnInit {
  private readonly agencyService = inject(AgencyService);
  private readonly notify = inject(NotifyService);

  readonly tenantId = input.required<string>();
  /** Named in the dialog's title, so it is clear which agency is being changed. */
  readonly agencyName = input.required<string>();
  /** A closed agency's modules are shown but not editable. */
  readonly readonly = input(false);

  protected readonly modules = signal<ModuleResponse[]>([]);
  protected readonly enabledCount = computed(() => this.modules().filter((m) => m.enabled).length);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  protected readonly dialogOpen = signal(false);
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
