import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConfirmationService } from 'primeng/api';
import { ButtonDirective } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { catchError, of, switchMap, tap } from 'rxjs';
import {
  AdminCylinderTypeService,
  NotifyService,
  errorMessageFor,
  type CylinderSizeResponse,
  type CylinderTypeResponse,
  type CylinderTypeUsageResponse,
} from '@lpg/shared/data-access';
import { DrawerA11yDirective, FormFieldComponent, validateForSubmit } from '@lpg/shared/ui';
import {
  GST_RATE_HINT,
  GST_RATE_MESSAGES,
  HSN_MESSAGES,
  HSN_PATTERN,
  LPG_HSN_CODE,
  categoryLabel,
  categoryOptions,
  sizesIn,
  joinWithAnd,
  sizesNotTaken,
  weightLabel,
} from './cylinder-type-fields';

/**
 * One cylinder type: its details, and editing, deactivating and deleting it.
 * A type that something refers to keeps its size and cannot be deleted — the
 * API says which applies (ADR-079).
 */
@Component({
  selector: 'lpg-cylinder-type-drawer',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonDirective,
    Drawer,
    DrawerA11yDirective,
    FormFieldComponent,
    InputText,
    Select,
    Tag,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p-drawer
      [visible]="!!cylinderType()"
      (onHide)="closed.emit()"
      position="right"
      [modal]="true"
      [closeOnEscape]="true"
      [header]="editing() ? 'Edit cylinder type' : 'Cylinder type'"
      styleClass="w-full"
      [style]="{ width: '100%', maxWidth: '32rem' }"
    >
      @if (cylinderType(); as type) {
        @if (editing()) {
          <form [formGroup]="form" (ngSubmit)="save()" novalidate class="dialog-form">
            <div class="dialog-form__fields">
              <p class="page-lede">
                Changes to <strong>{{ type.name }}</strong> apply from now on. Invoices already
                issued are not changed.
              </p>
              <lpg-form-field
                label="Cylinder type"
                for="edit-cylinder-category"
                [control]="form.controls.category"
              >
                <p-select
                  inputId="edit-cylinder-category"
                  formControlName="category"
                  [options]="editCategories()"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="Choose a type"
                  emptyMessage="No other type can be chosen."
                  appendTo="body"
                  [fluid]="true"
                />
              </lpg-form-field>
              <lpg-form-field
                label="Cylinder size"
                for="edit-cylinder-size"
                [control]="form.controls.sizeCode"
                [hint]="sizeHint()"
                [messages]="{ required: 'Choose a cylinder size.' }"
              >
                <p-select
                  inputId="edit-cylinder-size"
                  formControlName="sizeCode"
                  [options]="editSizes()"
                  optionLabel="name"
                  optionValue="code"
                  [placeholder]="type.size_code ? 'Choose a size' : type.name"
                  emptyMessage="Choose a cylinder type first."
                  appendTo="body"
                  [fluid]="true"
                />
              </lpg-form-field>
              <lpg-form-field
                label="HSN code"
                for="edit-cylinder-hsn"
                [control]="form.controls.hsnCode"
                [messages]="hsnMessages"
              >
                <input
                  pInputText
                  id="edit-cylinder-hsn"
                  inputmode="numeric"
                  formControlName="hsnCode"
                  [fluid]="true"
                />
              </lpg-form-field>
              <lpg-form-field
                label="GST rate (%)"
                for="edit-cylinder-gst"
                [control]="form.controls.gstRatePercent"
                [hint]="gstHint"
                [messages]="gstMessages"
              >
                <input
                  pInputText
                  id="edit-cylinder-gst"
                  type="number"
                  step="0.01"
                  formControlName="gstRatePercent"
                  [fluid]="true"
                />
              </lpg-form-field>
            </div>
            <div class="modal-actions">
              <button pButton type="button" severity="secondary" (click)="editing.set(false)">
                Cancel
              </button>
              <button pButton type="submit" [disabled]="saving()">
                @if (saving()) {
                  <i class="pi pi-spin pi-spinner" aria-hidden="true"></i>
                }
                Save changes
              </button>
            </div>
          </form>
        } @else {
          <div class="detail">
            <div>
              <h2 class="detail__name">{{ type.name }}</h2>
              <div class="detail__tags">
                <p-tag
                  [severity]="type.is_active ? 'success' : 'warn'"
                  [value]="type.is_active ? 'Active' : 'Inactive'"
                />
                @if (!type.size_code) {
                  <p-tag severity="warn" value="Not a standard size" />
                }
              </div>
            </div>

            <div class="detail__actions">
              <button
                pButton
                type="button"
                size="small"
                data-action="edit"
                [disabled]="!usage()"
                (click)="startEdit(type)"
              >
                <i class="pi pi-pencil" aria-hidden="true"></i>
                <span>Edit</span>
              </button>
              <button
                pButton
                type="button"
                size="small"
                severity="secondary"
                data-action="toggle-active"
                (click)="activeToggled.emit(type)"
              >
                <i
                  class="pi"
                  [class.pi-ban]="type.is_active"
                  [class.pi-check-circle]="!type.is_active"
                  aria-hidden="true"
                ></i>
                <span>{{ type.is_active ? 'Deactivate' : 'Activate' }}</span>
              </button>
              <button
                pButton
                type="button"
                size="small"
                severity="danger"
                data-action="delete"
                [disabled]="!canDelete()"
                [attr.aria-describedby]="deleteBlockedReason() ? 'cylinder-delete-reason' : null"
                (click)="confirmDelete(type)"
              >
                <i class="pi pi-trash" aria-hidden="true"></i>
                <span>Delete</span>
              </button>
            </div>

            @if (deleteBlockedReason(); as reason) {
              <p class="detail__note" id="cylinder-delete-reason">{{ reason }}</p>
            }
            @if (usageError(); as error) {
              <div class="detail__note" role="alert">
                <span>Couldn't check where this type is used. {{ error }}</span>
                <button pButton type="button" size="small" severity="secondary" (click)="retry()">
                  Retry
                </button>
              </div>
            }
            @if (offListAdvice(); as advice) {
              <p class="detail__warning" role="status">
                <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
                <span>{{ advice }}</span>
              </p>
            }

            <dl class="detail__grid">
              <div>
                <dt>Category</dt>
                <dd>{{ category(type.category) }}</dd>
              </div>
              <div>
                <dt>Gas weight</dt>
                <dd>{{ weight(type.weight_kg) }}</dd>
              </div>
              <div>
                <dt>HSN code</dt>
                <dd>{{ type.hsn_code ?? 'Not set' }}</dd>
              </div>
              <div>
                <dt>GST rate</dt>
                <dd>{{ gstRate(type) }}</dd>
              </div>
            </dl>
          </div>
        }
      }
    </p-drawer>
  `,
  styles: [
    `
      .detail {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .detail__name {
        margin: 0 0 var(--spacing-xs);
        font-size: var(--typography-heading2-font-size);
        font-weight: var(--typography-heading2-font-weight);
      }

      .detail__tags,
      .detail__actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .detail__note {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm);
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
        line-height: var(--typography-caption-line-height);
      }

      .detail__warning {
        display: flex;
        align-items: flex-start;
        gap: var(--spacing-sm);
        margin: 0;
        padding: var(--spacing-sm) var(--spacing-md);
        border: var(--border-width) solid var(--color-status-warning);
        border-radius: var(--radius-md);
      }

      .detail__warning > .pi {
        color: var(--color-status-warning);
      }

      .detail__grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--spacing-md) var(--spacing-xl);
        margin: 0;
        padding-block: var(--spacing-md);
        border-block: var(--border-width) solid var(--color-border-default);
      }

      .detail__grid dt {
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }

      .detail__grid dd {
        margin: var(--spacing-xs) 0 0;
        color: var(--color-text-primary);
      }
    `,
  ],
})
export class CylinderTypeDrawer {
  /** The record shown; `null` closes the drawer. */
  readonly cylinderType = input<CylinderTypeResponse | null>(null);
  readonly allTypes = input<readonly CylinderTypeResponse[]>([]);
  readonly sizes = input<readonly CylinderSizeResponse[]>([]);

  readonly closed = output<void>();
  /** The record was edited; the list needs reloading. */
  readonly saved = output<void>();
  readonly deleted = output<void>();
  readonly activeToggled = output<CylinderTypeResponse>();

  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly notify = inject(NotifyService);
  private readonly confirmation = inject(ConfirmationService);

  protected readonly editing = signal(false);
  protected readonly saving = signal(false);
  protected readonly usage = signal<CylinderTypeUsageResponse | null>(null);
  protected readonly usageError = signal<string | null>(null);
  private readonly usageVersion = signal(0);
  private readonly typeId = computed(() => this.cylinderType()?.id ?? null);

  protected readonly gstHint = GST_RATE_HINT;
  protected readonly hsnMessages = HSN_MESSAGES;
  protected readonly gstMessages = GST_RATE_MESSAGES;
  protected readonly category = categoryLabel;
  protected readonly weight = weightLabel;

  protected readonly form = this.formBuilder.group({
    category: [null as string | null],
    sizeCode: [null as string | null],
    hsnCode: [LPG_HSN_CODE, [Validators.required, Validators.pattern(HSN_PATTERN)]],
    gstRatePercent: [null as number | null],
  });

  /** Sizes this record may take: allowed by its history, and not already added. */
  private readonly selectableSizes = computed(() => {
    const allowed = new Set(this.usage()?.allowed_size_codes ?? []);
    const others = this.allTypes().filter((other) => other.id !== this.typeId());
    return sizesNotTaken(
      this.sizes().filter((size) => allowed.has(size.code)),
      others,
    );
  });
  protected readonly editCategories = computed(() => categoryOptions(this.selectableSizes()));
  private readonly chosenCategory = toSignal(this.form.controls.category.valueChanges, {
    initialValue: null,
  });
  protected readonly editSizes = computed(() =>
    sizesIn(this.selectableSizes(), this.chosenCategory()),
  );
  /** The type shown when editing began. */
  private startingCategory: string | null = null;

  protected readonly sizeHint = computed(() => {
    const type = this.cylinderType();
    const usage = this.usage();
    if (!type || !usage || usage.used_in.length === 0) return '';
    const hasAlternative = this.selectableSizes().some((size) => size.code !== type.size_code);
    if (!hasAlternative) return 'This cylinder type is in use, so its size cannot change.';
    return `This cylinder type is in use, so only ${weightLabel(type.weight_kg)} sizes can be chosen.`;
  });

  protected readonly canDelete = computed(() => this.usage()?.used_in.length === 0);

  protected readonly deleteBlockedReason = computed(() => {
    const usedIn = this.usage()?.used_in ?? [];
    if (usedIn.length === 0) return null;
    const reason = `It is used in ${joinWithAnd(usedIn)}, so it cannot be deleted.`;
    return this.cylinderType()?.is_active ? `${reason} Deactivate it instead.` : reason;
  });

  /** What to do about a record typed before the standard list existed. */
  protected readonly offListAdvice = computed(() => {
    const type = this.cylinderType();
    const usage = this.usage();
    if (!type || type.size_code || !usage) return null;
    const problem = `“${type.name}” is not a standard cylinder size.`;
    if (this.selectableSizes().length > 0) {
      return `${problem} Choose Edit and pick its size.`;
    }
    if (usage.allowed_size_codes.length === 0) {
      return `${problem} No standard size weighs ${weightLabel(type.weight_kg)} and this record is in use, so deactivate it and add a standard size.`;
    }
    return `${problem} The matching standard size is already in your list, so deactivate this one and use that.`;
  });

  constructor() {
    // A size belongs to one type, so changing the type clears the size.
    this.form.controls.category.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.form.controls.sizeCode.reset(null));

    effect(() => {
      this.typeId();
      untracked(() => this.editing.set(false));
    });

    toObservable(computed(() => ({ id: this.typeId(), version: this.usageVersion() })))
      .pipe(
        tap(() => {
          this.usage.set(null);
          this.usageError.set(null);
        }),
        // switchMap: a slow answer for the previous record is dropped.
        switchMap(({ id }) =>
          id
            ? this.cylinderTypeService.getUsage(id).pipe(
                catchError((error: unknown) => {
                  this.usageError.set(errorMessageFor(error));
                  return of(null);
                }),
              )
            : of(null),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((usage) => this.usage.set(usage));
  }

  protected retry(): void {
    this.usageVersion.update((version) => version + 1);
  }

  protected gstRate(type: CylinderTypeResponse): string {
    return type.gst_rate_percent == null ? 'Not set' : `${Number(type.gst_rate_percent)}%`;
  }

  protected startEdit(type: CylinderTypeResponse): void {
    const rate = this.form.controls.gstRatePercent;
    // A rate that is set can be corrected, not removed.
    rate.setValidators([
      Validators.min(0),
      Validators.max(28),
      ...(type.gst_rate_percent == null ? [] : [Validators.required]),
    ]);
    // A record typed by hand has no type; pick it when only one is possible.
    const choices = this.editCategories();
    this.startingCategory = type.category ?? (choices.length === 1 ? choices[0].value : null);
    this.form.reset({
      category: this.startingCategory,
    });
    // After the type: choosing a type clears the size.
    this.form.patchValue({
      sizeCode: type.size_code ?? null,
      hsnCode: type.hsn_code ?? LPG_HSN_CODE,
      gstRatePercent: type.gst_rate_percent == null ? null : Number(type.gst_rate_percent),
    });
    this.editing.set(true);
  }

  protected save(): void {
    const type = this.cylinderType();
    if (!type || this.saving() || !validateForSubmit(this.form)) return;

    const { category, sizeCode, hsnCode, gstRatePercent } = this.form.getRawValue();
    // A new type without a size would otherwise be dropped without a word.
    if (!sizeCode && category !== this.startingCategory) {
      this.form.controls.sizeCode.setErrors({ required: true });
      this.form.controls.sizeCode.markAsTouched();
      return;
    }
    const newSize = sizeCode && sizeCode !== type.size_code ? sizeCode : undefined;
    const hasRate = gstRatePercent != null && String(gstRatePercent) !== '';
    const gstChanged =
      hasRate &&
      (type.gst_rate_percent == null ||
        Number(gstRatePercent) !== Number(type.gst_rate_percent) ||
        hsnCode !== type.hsn_code);
    if (!newSize && !gstChanged) {
      this.editing.set(false);
      return;
    }

    this.saving.set(true);
    this.cylinderTypeService
      .updateCylinderType(type.id, {
        sizeCode: newSize,
        gst: gstChanged ? { hsnCode, gstRatePercent: Number(gstRatePercent) } : undefined,
      })
      .subscribe({
        next: (updated) => {
          this.saving.set(false);
          this.editing.set(false);
          this.notify.success(`"${updated.name}" saved.`);
          this.usageVersion.update((version) => version + 1);
          this.saved.emit();
        },
        error: () => this.saving.set(false),
      });
  }

  protected confirmDelete(type: CylinderTypeResponse): void {
    this.confirmation.confirm({
      header: 'Delete cylinder type?',
      message: `"${type.name}" will be removed from your cylinder types.`,
      acceptLabel: 'Delete',
      rejectLabel: 'Cancel',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () =>
        this.cylinderTypeService.deleteCylinderType(type.id).subscribe({
          next: () => {
            this.notify.success(`"${type.name}" deleted.`);
            this.deleted.emit();
          },
          // The error is toasted globally; something may now refer to it.
          error: () => this.retry(),
        }),
    });
  }
}
