import { HeaderPortalDirective, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin, of, type Observable } from 'rxjs';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { Select } from 'primeng/select';
import { DatePicker } from 'primeng/datepicker';
import { MessageService } from 'primeng/api';
import {
  AdminFeatureFlagService,
  type AppError,
  type FeatureFlagResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, formatTimestamp } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the flag. Please try again.';
  }
}

/** `dd-mm-yyyy`-picker value → ISO date string, or `null` for an empty/
 * cleared field. */
function formatDateForApi(value: unknown): string | null {
  if (!value) return null;
  const dateObj = new Date(value as string | number | Date);
  const year = dateObj.getFullYear();
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** AG Grid renders a boolean-valued column with its own checkbox cell by
 * default, ignoring `valueFormatter` — this swaps that for the plain
 * "Enabled"/"Disabled" text a flags table reads as. */
@Component({
  selector: 'lpg-flag-default-cell',
  standalone: true,
  template: `{{ label() }}`,
})
class FlagDefaultCell {
  protected readonly label = signal('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    this.label.set(params.value ? 'Enabled' : 'Disabled');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}

/**
 * Platform-wide feature flag management — `feature_flags:manage_platform`,
 * `super_admin` only, live-checked server-side (same high-sensitivity
 * pattern `reconciliation:approve` uses).
 *
 * The whole page is already gated by this permission (the route itself
 * requires it — `app.routes.ts`), so unlike the Driver/Vehicle details
 * drawers elsewhere in this app, there's no *further* inner RBAC gate on
 * the Edit action here: reaching this page at all already means you hold
 * the permission every mutation below also requires.
 */
@Component({
  selector: 'lpg-platform-flags-page',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    HeaderPortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Drawer,
    Select,
    DatePicker,
    DataGridComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Platform Feature Flags</h1>
          <p class="page-subtitle">Manage platform-wide feature flags and rollout percentages.</p>
        </div>
    </ng-template>
        <ng-template lpgHeaderPortal>
  <div class="page-header__actions">
            <button pButton (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Create Flag</span></button>
          </div>
</ng-template>
      </div>

      <section class="grid-section">
        <div class="grid-wrapper">
          <lpg-data-grid
            [rows]="flags()"
            [columns]="columns"
            [loading]="loading()"
            ariaLabel="Feature flags"
          />
        </div>
      </section>

      <!-- Create Flag Drawer -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Create a flag"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="createFlagForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <div class="form-group">
            <label for="flag-key">Key</label>
            <input pInputText id="flag-key" type="text" formControlName="key" />
            @if (form.controls.key.touched && form.controls.key.invalid) {
              <small class="field-error">Key is required.</small>
            }
          </div>
          <div class="form-group">
            <label for="flag-description">Description</label>
            <input pInputText id="flag-description" type="text" formControlName="description" />
            @if (form.controls.description.touched && form.controls.description.invalid) {
              <small class="field-error">Description is required.</small>
            }
          </div>
          <div class="form-group">
            <label for="flag-rollout">Rollout % (optional)</label>
            <input
              pInputText
              id="flag-rollout"
              type="number"
              min="0"
              max="100"
              formControlName="rolloutPercentage"
            />
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="createDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
              Create flag
            </button>
          </div>
        </form>
      </p-drawer>

      <!-- Flag Details Drawer -->
      <p-drawer
        header="Flag Details"
        [visible]="showDetailDrawer()"
        (onHide)="closeDetails()"
        position="right"
        [modal]="true"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        @if (selectedFlag(); as flag) {
          @if (!editMode()) {
            <div class="detail-view">
              <div class="detail-item">
                <span class="detail-label">Key</span>
                <span class="detail-value">{{ flag.key }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Description</span>
                <span class="detail-value">{{ flag.description }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Default</span>
                <span class="detail-value">{{ flag.is_enabled_by_default ? 'Enabled' : 'Disabled' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Rollout %</span>
                <span class="detail-value">{{ flag.rollout_percentage ?? '—' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Starts At</span>
                <span class="detail-value">{{ flag.starts_at ? formatTimestamp(flag.starts_at) : 'Not scheduled' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Ends At</span>
                <span class="detail-value">{{ flag.ends_at ? formatTimestamp(flag.ends_at) : 'Not scheduled' }}</span>
              </div>

              <div class="modal-actions">
                <button pButton type="button" severity="secondary" (click)="closeDetails()">Close</button>
                <button pButton type="button" (click)="startEdit()">
                  <i pButtonIcon class="pi pi-pencil"></i>
                  <span pButtonLabel>Edit</span>
                </button>
              </div>
            </div>
          } @else {
            <form id="editFlagForm" [formGroup]="editForm" (ngSubmit)="saveEdit()" class="dialog-form">
              <div class="form-group">
                <label for="edit_default">Default</label>
                <p-select
                  id="edit_default"
                  formControlName="isEnabledByDefault"
                  [options]="[
                    { label: 'Enabled', value: true },
                    { label: 'Disabled', value: false }
                  ]"
                  optionLabel="label"
                  optionValue="value"
                ></p-select>
              </div>

              <div class="form-group">
                <label for="edit_rollout">Rollout % (optional)</label>
                <input
                  pInputText
                  id="edit_rollout"
                  type="number"
                  min="0"
                  max="100"
                  formControlName="rolloutPercentage"
                />
              </div>

              <div class="form-group">
                <label for="edit_starts_at">Starts At (optional)</label>
                <p-datepicker
                  id="edit_starts_at"
                  formControlName="startsAt"
                  [showIcon]="true"
                  iconDisplay="input"
                  dateFormat="dd-mm-yy"
                  placeholder="dd-mm-yyyy"
                  appendTo="body"
                  [fluid]="true"
                ></p-datepicker>
              </div>

              <div class="form-group">
                <label for="edit_ends_at">Ends At (optional)</label>
                <p-datepicker
                  id="edit_ends_at"
                  formControlName="endsAt"
                  [showIcon]="true"
                  iconDisplay="input"
                  dateFormat="dd-mm-yy"
                  placeholder="dd-mm-yyyy"
                  appendTo="body"
                  [fluid]="true"
                ></p-datepicker>
              </div>

              <div class="modal-actions">
                <button pButton type="button" severity="secondary" (click)="cancelEdit()">Cancel</button>
                <button pButton type="submit" [disabled]="editForm.invalid || saving()">Save Changes</button>
              </div>
            </form>
          }
        }
      </p-drawer>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .grid-section {
        margin-block-start: var(--spacing-lg);
      }

      .grid-wrapper {
        block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }

      .detail-view {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        flex: 1;
      }

      .detail-item {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
      }

      .detail-label {
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .detail-value {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-primary);
      }
    `,
  ],
})
export class PlatformFlagsPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly featureFlagService = inject(AdminFeatureFlagService);
  private readonly messageService = inject(MessageService);

  protected readonly formatTimestamp = formatTimestamp;

  protected readonly flags = signal<FeatureFlagResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);

  // Details drawer — view mode shows the flag's current state (with an
  // Edit button), edit mode swaps in a form covering default/rollout/
  // schedule. Each goes through its own backend endpoint, so saveEdit()
  // only calls whichever endpoint(s) actually changed.
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedFlag = signal<FeatureFlagResponse | null>(null);
  protected readonly editMode = signal(false);
  protected readonly saving = signal(false);

  protected readonly columns: DataGridColumn<FeatureFlagResponse>[] = [
    { field: 'key', header: 'Key', sortable: true, filterable: true, onLinkClick: (row) => this.openDetails(row) },
    { field: 'description', header: 'Description' },
    {
      field: 'is_enabled_by_default',
      header: 'Default',
      sortable: true,
      cellRenderer: FlagDefaultCell,
    },
    {
      field: 'rollout_percentage',
      header: 'Rollout %',
      numeric: true,
      valueFormatter: (value) => (value === null || value === undefined ? '—' : String(value)),
    },
  ];

  protected readonly form = this.formBuilder.group({
    key: ['', [Validators.required]],
    description: ['', [Validators.required]],
    rolloutPercentage: [null as number | null],
  });

  protected readonly editForm = this.formBuilder.group({
    isEnabledByDefault: [false, [Validators.required]],
    rolloutPercentage: [null as number | null],
    startsAt: this.formBuilder.control<Date | null>(null),
    endsAt: this.formBuilder.control<Date | null>(null),
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.featureFlagService.listFlags().subscribe({
      next: (flags) => {
        this.flags.set(flags);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected openCreateDrawer(): void {
    this.form.reset();
    this.createDrawerVisible.set(true);
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    const { key, description, rolloutPercentage } = this.form.getRawValue();

    this.featureFlagService.createFlag(key, description, false, rolloutPercentage).subscribe({
      next: () => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `Flag "${key}" created.` });
        this.createDrawerVisible.set(false);
        this.form.reset();
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected openDetails(flag: FeatureFlagResponse): void {
    this.selectedFlag.set(flag);
    this.editMode.set(false);
    this.showDetailDrawer.set(true);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
    this.editMode.set(false);
  }

  protected startEdit(): void {
    const flag = this.selectedFlag();
    if (!flag) return;
    this.editForm.reset({
      isEnabledByDefault: flag.is_enabled_by_default,
      rolloutPercentage: flag.rollout_percentage,
      startsAt: flag.starts_at ? new Date(flag.starts_at) : null,
      endsAt: flag.ends_at ? new Date(flag.ends_at) : null,
    });
    this.editMode.set(true);
  }

  protected cancelEdit(): void {
    this.editMode.set(false);
  }

  /** Calls whichever of the three backend endpoints (default, rollout,
   * schedule) the changed fields actually need — there's no single "update
   * everything" endpoint, so an unchanged field isn't sent. */
  protected saveEdit(): void {
    const flag = this.selectedFlag();
    if (!flag || this.editForm.invalid) return;

    const val = this.editForm.getRawValue();
    const newStartsAt = formatDateForApi(val.startsAt);
    const newEndsAt = formatDateForApi(val.endsAt);
    const defaultChanged = val.isEnabledByDefault !== flag.is_enabled_by_default;
    const rolloutChanged = val.rolloutPercentage !== flag.rollout_percentage;
    const scheduleChanged = newStartsAt !== flag.starts_at || newEndsAt !== flag.ends_at;

    if (!defaultChanged && !rolloutChanged && !scheduleChanged) {
      this.editMode.set(false);
      return;
    }

    const requests: Observable<void>[] = [];
    if (defaultChanged) {
      requests.push(this.featureFlagService.setEnabledByDefault(flag.key, val.isEnabledByDefault));
    }
    if (rolloutChanged) {
      requests.push(this.featureFlagService.setRolloutPercentage(flag.key, val.rolloutPercentage));
    }
    if (scheduleChanged) {
      requests.push(this.featureFlagService.schedule(flag.key, newStartsAt, newEndsAt));
    }

    this.saving.set(true);
    forkJoin(requests.length > 0 ? requests : [of(undefined)]).subscribe({
      next: () => {
        this.featureFlagService.listFlags().subscribe({
          next: (flags) => {
            this.flags.set(flags);
            this.selectedFlag.set(flags.find((f) => f.key === flag.key) ?? null);
            this.editMode.set(false);
            this.saving.set(false);
            this.messageService.add({ severity: 'success', summary: 'Success', detail: `Flag "${flag.key}" updated.` });
          },
        });
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
