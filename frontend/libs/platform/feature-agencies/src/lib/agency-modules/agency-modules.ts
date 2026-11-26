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
            {{ savedCount() }} of {{ modules().length }} on
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
      (visibleChange)="$event ? dialogOpen.set(true) : close()"
      (onHide)="openButton.focus()"
      [header]="'Modules · ' + agencyName()"
      [modal]="true"
      [closeOnEscape]="true"
      [draggable]="false"
      [resizable]="false"
      appendTo="body"
      [style]="{ width: '56rem', maxWidth: '95vw' }"
    >
      <!-- While saving, "inert" blocks edits without restyling every switch. -->
      <div [attr.inert]="saving() ? '' : null">
        <div class="toolbar">
          <p class="hint toolbar__hint">
            Switched-off modules are hidden from this agency and blocked. Home, Notifications,
            Settings and the Administration screens are always available. A locked switch depends on
            the modules named under it. Changes apply when you save.
          </p>
          @if (!readonly()) {
            <div class="master">
              <div class="module__text">
                <label class="module__label" for="agency-modules-all">All modules</label>
                <span id="agency-modules-all-state" class="hint">{{ allState() }}</span>
              </div>
              <p-toggleswitch
                inputId="agency-modules-all"
                ariaDescribedBy="agency-modules-all-state"
                [ngModel]="allOn()"
                (onChange)="setAll($event.checked)"
              />
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
                  @if (dependencyNotes()[module.key]; as note) {
                    <span class="hint module__note">{{ note }}</span>
                  }
                </div>
                <p-toggleswitch
                  [ngModel]="module.enabled"
                  [disabled]="readonly() || locked(module)"
                  [ariaLabel]="module.label"
                  (onChange)="toggle(module, $event.checked)"
                />
              </li>
            }
          </ul>
        }
      </div>

      <ng-template #footer>
        <div class="footer">
          <span class="hint" aria-live="polite">
            {{ enabledCount() }} of {{ modules().length }} on
            @if (changeCount(); as count) {
              · {{ count }} unsaved {{ count === 1 ? 'change' : 'changes' }}
            }
          </span>
          <div class="footer__actions">
            <button
              pButton
              type="button"
              severity="secondary"
              [disabled]="saving()"
              (click)="close()"
            >
              <span>{{ readonly() ? 'Close' : 'Cancel' }}</span>
            </button>
            @if (!readonly()) {
              <button
                pButton
                type="button"
                class="footer__save"
                [attr.aria-busy]="saving()"
                [disabled]="saving() || changeCount() === 0"
                (click)="save()"
              >
                <!-- Always an icon, so the button keeps its width when it spins. -->
                <i
                  class="pi"
                  [class]="saving() ? 'pi-spin pi-spinner' : 'pi-check'"
                  aria-hidden="true"
                ></i>
                <span>Save changes</span>
              </button>
            }
          </div>
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

      .master {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-lg);
        inline-size: min(100%, 22rem);
        padding: var(--spacing-sm) var(--spacing-md);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-input);
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
        flex-wrap: wrap;
        gap: var(--spacing-md);
        inline-size: 100%;
      }

      .footer__actions {
        display: flex;
        gap: var(--spacing-sm);
        margin-inline-start: auto;
      }

      /* The checkmark and the spinner are not quite the same width. */
      .footer__save .pi {
        display: inline-grid;
        place-items: center;
        inline-size: 1.25em;
        block-size: 1.25em;
      }

      /* On a phone the count always has its own line, so a longer count never
         moves the buttons down. */
      @media (max-width: 36rem) {
        .footer > .hint {
          flex-basis: 100%;
        }
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

  /** The modules as the server has them. */
  private readonly saved = signal<ModuleResponse[]>([]);
  /** Switches changed in the dialog and not saved yet: module key to new state. */
  private readonly edits = signal<Readonly<Record<string, boolean>>>({});
  protected readonly changeCount = computed(() => Object.keys(this.edits()).length);
  protected readonly saving = signal(false);
  protected readonly savedCount = computed(() => this.saved().filter((m) => m.enabled).length);
  /** What the dialog shows: the saved modules with the edits on top. */
  protected readonly modules = computed(() => withChanges(this.saved(), this.edits()));
  protected readonly enabledCount = computed(() => this.modules().filter((m) => m.enabled).length);
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  protected readonly dialogOpen = signal(false);
  protected readonly allOn = computed(
    () => this.modules().length > 0 && this.enabledCount() === this.modules().length,
  );
  /** Says what the "All modules" switch will do from here. */
  protected readonly allState = computed(() => {
    if (this.allOn()) return 'All on. Switch off to turn all off.';
    if (this.enabledCount() === 0) return 'All off. Switch on to turn all on.';
    return 'Some on. Switch on to turn the rest on.';
  });

  /* Which modules each one needs, and which need it. Built from the catalog,
     not from what is switched on: a note that came and went as switches moved
     changed the dialog's height, and the whole dialog jumped. */
  protected readonly dependencyNotes = computed(() => {
    const modules = this.saved();
    const labels = (list: ModuleResponse[]) => list.map((m) => m.label).join(', ');
    return Object.fromEntries(
      modules.map((module) => {
        const needs = modules.filter((m) => module.requires.includes(m.key));
        const neededBy = modules.filter((m) => m.requires.includes(module.key));
        const parts = [
          needs.length ? `Needs ${labels(needs)}.` : '',
          neededBy.length ? `Needed by ${labels(neededBy)}.` : '',
        ];
        return [module.key, parts.filter(Boolean).join(' ')];
      }),
    );
  });

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
        this.saved.set(modules);
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

  protected toggle(module: ModuleResponse, enabled: boolean): void {
    this.edit([module.key], enabled);
  }

  /** Turns every module on or off. Nothing is saved until Save. */
  protected setAll(enabled: boolean): void {
    this.edit(
      this.modules().map((m) => m.key),
      enabled,
    );
  }

  /** Closing the dialog, by any route, drops what was not saved. A save that
      is already on its way carries on. */
  protected close(): void {
    this.dialogOpen.set(false);
    if (!this.saving()) this.edits.set({});
  }

  protected save(): void {
    const changes = this.edits();
    this.saving.set(true);
    this.agencyService.setModules(this.tenantId(), changes).subscribe({
      next: () => {
        this.saved.update((modules) => withChanges(modules, changes));
        this.saving.set(false);
        this.notify.success(`Modules saved for ${this.agencyName()}.`);
        this.close();
      },
      // An open dialog keeps the edits, so they can be fixed or retried.
      error: (err) => {
        this.saving.set(false);
        if (!this.dialogOpen()) this.edits.set({});
        this.notify.error(errorMessageFor(err));
      },
    });
  }

  /** Keeps only real differences, so switching something back is not a change. */
  private edit(keys: readonly string[], enabled: boolean): void {
    const next = { ...this.edits() };
    for (const key of keys) {
      if (this.saved().find((m) => m.key === key)?.enabled === enabled) {
        delete next[key];
      } else {
        next[key] = enabled;
      }
    }
    this.edits.set(next);
  }
}

function withChanges(
  modules: readonly ModuleResponse[],
  changes: Readonly<Record<string, boolean>>,
): ModuleResponse[] {
  return modules.map((m) => (m.key in changes ? { ...m, enabled: changes[m.key] } : m));
}
