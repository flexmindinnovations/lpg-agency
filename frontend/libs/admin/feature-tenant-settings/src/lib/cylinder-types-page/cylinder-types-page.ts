import { ConfirmationService } from 'primeng/api';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
  viewChild,
  computed,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { Select } from 'primeng/select';
import {
  AdminCylinderTypeService,
  NotifyService,
  type CylinderSizeResponse,
  type CylinderTypeResponse,
  errorMessageFor,
} from '@lpg/shared/data-access';
import {
  DrawerA11yDirective,
  ExportButtonComponent,
  FormFieldComponent,
  HeaderTitlePortalDirective,
  PageActionsDirective,
  PageHeaderComponent,
} from '@lpg/shared/ui';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui/data-grid';
import { CylinderTypeDrawer } from './cylinder-type-drawer';
import {
  GST_RATE_HINT,
  GST_RATE_MESSAGES,
  HSN_MESSAGES,
  HSN_PATTERN,
  LPG_HSN_CODE,
  categoryOptions,
  sizesIn,
  sizesNotTaken,
} from './cylinder-type-fields';

/** AG Grid renders a boolean-valued column with its own checkbox cell by
 * default, ignoring `valueFormatter` (same issue fixed for Platform
 * Flags' "Default" column and Linked Devices' "Status" column) — this
 * swaps that for plain "Active"/"Inactive" text. */
@Component({
  selector: 'lpg-cylinder-type-status-cell',
  standalone: true,
  template: `{{ label() }}`,
})
class CylinderTypeStatusCell {
  protected readonly label = signal('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    this.label.set(params.value ? 'Active' : 'Inactive');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}

/** Cylinder types picked from the standard size list — `tenant:configure`. */
@Component({
  selector: 'lpg-cylinder-types-page',
  standalone: true,
  imports: [
    ExportButtonComponent,
    PageActionsDirective,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    DataGridComponent,
    FormFieldComponent,
    Drawer,
    DrawerA11yDirective,
    IconField,
    InputIcon,
    Select,
    CylinderTypeDrawer,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <lpg-page-header
            title="Cylinder Types"
            subtitle="The LPG cylinder sizes your agency deals in, and their GST."
          />
        </ng-template>
      </div>

      @if (unclassifiedCount() > 0) {
        <div class="gst-warning" role="status">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <span>
            {{ unclassifiedCount() }} cylinder
            {{ unclassifiedCount() === 1 ? 'type has' : 'types have' }} no GST rate. Deliveries of
            them are held, not invoiced, until you set one with “Set GST”.
          </span>
        </div>
      }

      @if (offList().length > 0) {
        <div class="gst-warning" role="status">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <span>
            Not a standard cylinder size: {{ offList().join(', ') }}. Select the name to fix it.
          </span>
        </div>
      }

      @if (cylinderTypes().length > 0) {
        <ng-template lpgPageActions>
          <button pButton (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Add Cylinder Type</span>
          </button>
        </ng-template>
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield>
              <p-inputicon class="pi pi-search" />
              <input
                pInputText
                type="text"
                placeholder="Search cylinder types..."
                class="w-full"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </p-iconfield>
            <span class="data-toolbar__spacer"></span>
            <lpg-export-button (export)="exportCsv()" />
          </div>
        </div>
      }

      @if (!loading() && !loadError() && cylinderTypes().length === 0) {
        <div class="empty-state">
          <i class="pi pi-box empty-state__icon"></i>
          <p class="empty-state__title">No cylinder types found</p>
          <p class="empty-state__description">
            Get started by adding the first cylinder size you deal in.
          </p>
          <button pButton class="mt-4" (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Add Cylinder Type</span>
          </button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="cylinderTypes()"
            [columns]="columns()"
            [loading]="loading()"
            [error]="loadError()"
            (retry)="reload()"
            [searchQuery]="searchQuery()"
            ariaLabel="Cylinder Types"
          />
        </section>
      }

      <!-- Create Cylinder Type Drawer -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Add a cylinder type"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form
          id="addCylinderTypeForm"
          [formGroup]="form"
          (ngSubmit)="submit()"
          novalidate
          class="dialog-form"
        >
          <div class="dialog-form__fields">
            <p class="page-lede">Pick from the standard LPG cylinder sizes.</p>

            @if (sizesError(); as error) {
              <div class="inline-note" role="alert">
                <span>Couldn't load the cylinder sizes. {{ error }}</span>
                <button
                  pButton
                  type="button"
                  size="small"
                  severity="secondary"
                  (click)="loadSizes()"
                >
                  Retry
                </button>
              </div>
            } @else if (sizes().length > 0 && availableSizes().length === 0) {
              <p class="inline-note" role="status">
                Every standard size is already in your cylinder types.
              </p>
            }

            <lpg-form-field
              label="Cylinder type"
              for="cylinder-category"
              [control]="form.controls.category"
              [messages]="{ required: 'Choose a cylinder type.' }"
            >
              <p-select
                inputId="cylinder-category"
                formControlName="category"
                [options]="availableCategories()"
                optionLabel="label"
                optionValue="value"
                placeholder="Choose a type"
                [emptyMessage]="noOptionsMessage()"
                appendTo="body"
                [fluid]="true"
              />
            </lpg-form-field>

            <lpg-form-field
              label="Cylinder size"
              for="cylinder-size"
              [control]="form.controls.sizeCode"
              [messages]="{ required: 'Choose a cylinder size.' }"
            >
              <p-select
                inputId="cylinder-size"
                formControlName="sizeCode"
                [options]="sizesOfChosenType()"
                optionLabel="name"
                optionValue="code"
                placeholder="Choose a size"
                [emptyMessage]="noOptionsMessage()"
                appendTo="body"
                [fluid]="true"
              />
            </lpg-form-field>

            <div class="gst-fields">
              <lpg-form-field
                label="HSN code"
                for="cylinder-hsn"
                [control]="form.controls.hsnCode"
                [messages]="hsnMessages"
              >
                <input
                  pInputText
                  id="cylinder-hsn"
                  inputmode="numeric"
                  formControlName="hsnCode"
                  [fluid]="true"
                />
              </lpg-form-field>
              <lpg-form-field
                label="GST rate (%)"
                for="cylinder-gst"
                [control]="form.controls.gstRatePercent"
                [hint]="gstHint"
                [messages]="gstMessages"
              >
                <input
                  pInputText
                  id="cylinder-gst"
                  type="number"
                  step="0.01"
                  formControlName="gstRatePercent"
                  [fluid]="true"
                />
              </lpg-form-field>
            </div>
          </div>

          <div class="modal-actions">
            <button
              pButton
              type="button"
              severity="secondary"
              (click)="createDrawerVisible.set(false)"
            >
              Cancel
            </button>
            <button pButton type="submit" [disabled]="submitting()">
              @if (submitting()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
              Save cylinder type
            </button>
          </div>
        </form>
      </p-drawer>

      <!-- Set GST (DA-06) -->
      <p-drawer
        [visible]="!!gstTarget()"
        (onHide)="gstTarget.set(null)"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Set GST"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form [formGroup]="gstForm" (ngSubmit)="saveGst()" novalidate class="dialog-form">
          <div class="dialog-form__fields">
            <p class="page-lede">
              Invoices for <strong>{{ gstTarget()?.name }}</strong> use this HSN code and rate from
              now on. Invoices already issued are not changed.
            </p>
            <lpg-form-field
              label="HSN code"
              for="gst-hsn"
              [control]="gstForm.controls.hsnCode"
              [messages]="hsnMessages"
            >
              <input
                pInputText
                id="gst-hsn"
                inputmode="numeric"
                formControlName="hsnCode"
                [fluid]="true"
              />
            </lpg-form-field>
            <lpg-form-field
              label="GST rate (%)"
              for="gst-rate"
              [control]="gstForm.controls.gstRatePercent"
              [hint]="gstHint"
              [messages]="gstMessages"
            >
              <input
                pInputText
                id="gst-rate"
                type="number"
                step="0.01"
                formControlName="gstRatePercent"
                [fluid]="true"
              />
            </lpg-form-field>
          </div>
          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="gstTarget.set(null)">
              Cancel
            </button>
            <button pButton type="submit" [disabled]="submitting() || gstForm.invalid">
              @if (submitting()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
              Save GST
            </button>
          </div>
        </form>
      </p-drawer>

      <lpg-cylinder-type-drawer
        [cylinderType]="details()"
        [allTypes]="cylinderTypes()"
        [sizes]="sizes()"
        (closed)="detailsId.set(null)"
        (saved)="reload()"
        (deleted)="onDeleted()"
        (activeToggled)="toggleActive($event)"
      />
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }

      .admin-page {
        display: flex;
        flex-direction: column;
        block-size: 100%;
      }

      .gst-warning {
        display: flex;
        gap: var(--spacing-sm);
        align-items: flex-start;
        margin-block-end: var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-md);
        border: var(--border-width) solid var(--color-status-warning);
        border-radius: var(--radius-md);
      }

      .gst-warning > .pi {
        color: var(--color-status-warning);
      }

      :host ::ng-deep .cell--warning {
        color: var(--color-status-warning);
      }

      .inline-note {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm);
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }

      .gst-fields {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
        gap: var(--spacing-md);
      }
    `,
  ],
})
export class CylinderTypesPage implements OnInit {
  private readonly grid = viewChild(DataGridComponent);

  /** DA-14: the grid as shown (filtered, sorted, formatted) as a CSV file. */
  protected exportCsv(): void {
    this.grid()?.exportCsv('cylinder-types');
  }

  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly notify = inject(NotifyService);
  private readonly confirmation = inject(ConfirmationService);

  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly loading = signal(false);
  /** Set when the list failed to load — the grid shows it with Retry (QA DA-15). */
  protected readonly loadError = signal<string | null>(null);
  protected readonly searchQuery = signal('');
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);
  protected readonly gstTarget = signal<CylinderTypeResponse | null>(null);
  protected readonly unclassifiedCount = computed(
    () => this.cylinderTypes().filter((c) => c.is_active && c.gst_rate_percent == null).length,
  );

  protected readonly sizes = signal<CylinderSizeResponse[]>([]);
  protected readonly sizesError = signal<string | null>(null);
  /** Standard sizes the agency has not added yet. */
  protected readonly availableSizes = computed(() =>
    sizesNotTaken(this.sizes(), this.cylinderTypes()),
  );
  protected readonly availableCategories = computed(() => categoryOptions(this.availableSizes()));
  /** Active records typed before the standard list existed. */
  protected readonly offList = computed(() =>
    this.cylinderTypes()
      .filter((c) => c.is_active && !c.size_code)
      .map((c) => c.name),
  );

  protected readonly detailsId = signal<string | null>(null);
  /** Looked up in the list, so the drawer follows a reload. */
  protected readonly details = computed(
    () => this.cylinderTypes().find((c) => c.id === this.detailsId()) ?? null,
  );

  protected readonly gstHint = GST_RATE_HINT;
  protected readonly hsnMessages = HSN_MESSAGES;
  protected readonly gstMessages = GST_RATE_MESSAGES;

  protected readonly columns = computed<DataGridColumn<CylinderTypeResponse>[]>(() => {
    // "Set GST" is a first-time shortcut; later changes are made in the drawer.
    const needsGst = this.cylinderTypes().some((c) => c.gst_rate_percent == null);
    const setGst: DataGridColumn<CylinderTypeResponse> = {
      field: 'gst_action',
      header: '',
      valueFormatter: (_value, row) => (row.gst_rate_percent == null ? 'Set GST' : ''),
      onLinkClick: (row) => this.openGstDrawer(row),
    };
    return [
      {
        field: 'name',
        header: 'Name',
        sortable: true,
        filterable: true,
        // Wide enough for the longest standard size name.
        minWidth: 230,
        onLinkClick: (row) => this.detailsId.set(row.id),
      },
      { field: 'weight_kg', header: 'Weight (kg)', sortable: true, numeric: true },
      {
        field: 'hsn_code',
        header: 'HSN',
        sortable: true,
        valueFormatter: (value) => (value as string | null) ?? '—',
      },
      {
        field: 'gst_rate_percent',
        header: 'GST',
        sortable: true,
        numeric: true,
        valueFormatter: (value) => (value == null ? 'Not set' : `${Number(value)}%`),
        cellClass: (value) => (value == null ? 'cell--warning' : ''),
      },
      ...(needsGst ? [setGst] : []),
      {
        field: 'is_active',
        header: 'Status',
        sortable: true,
        cellRenderer: CylinderTypeStatusCell,
      },
      {
        field: 'id',
        header: '',
        valueFormatter: (_value, row) => (row.is_active ? 'Deactivate' : 'Activate'),
        onLinkClick: (row) => this.toggleActive(row),
      },
    ];
  });

  protected readonly form = this.formBuilder.group({
    category: [null as string | null, [Validators.required]],
    sizeCode: [null as string | null, [Validators.required]],
    hsnCode: [LPG_HSN_CODE, [Validators.required, Validators.pattern(HSN_PATTERN)]],
    gstRatePercent: [
      null as number | null,
      [Validators.required, Validators.min(0), Validators.max(28)],
    ],
  });

  private readonly chosenCategory = toSignal(this.form.controls.category.valueChanges, {
    initialValue: null,
  });
  protected readonly sizesOfChosenType = computed(() =>
    sizesIn(this.availableSizes(), this.chosenCategory()),
  );
  /** What an empty dropdown says, in place of "No results found". */
  protected readonly noOptionsMessage = computed(() => {
    if (this.sizesError()) return "The sizes didn't load. Use Retry above.";
    return this.chosenCategory() ? 'No sizes left to add.' : 'Choose a cylinder type first.';
  });

  constructor() {
    // A size belongs to one type, so changing the type clears the size.
    this.form.controls.category.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.form.controls.sizeCode.reset(null));
  }

  protected readonly gstForm = this.formBuilder.group({
    hsnCode: [LPG_HSN_CODE, [Validators.required, Validators.pattern(HSN_PATTERN)]],
    gstRatePercent: [
      null as number | null,
      [Validators.required, Validators.min(0), Validators.max(28)],
    ],
  });

  ngOnInit(): void {
    this.reload();
    this.loadSizes();
  }

  protected loadSizes(): void {
    this.sizesError.set(null);
    this.cylinderTypeService.listCylinderSizes().subscribe({
      next: (sizes) => this.sizes.set(sizes),
      error: (error: unknown) => this.sizesError.set(errorMessageFor(error)),
    });
  }

  protected onDeleted(): void {
    this.detailsId.set(null);
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (cylinderTypes) => {
        this.cylinderTypes.set(cylinderTypes);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(errorMessageFor(error));
        this.loading.set(false);
      },
    });
  }

  protected openCreateDrawer(): void {
    this.resetCreateForm();
    this.createDrawerVisible.set(true);
  }

  private resetCreateForm(): void {
    this.form.reset({
      category: null,
      sizeCode: null,
      hsnCode: LPG_HSN_CODE,
      gstRatePercent: null,
    });
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    const { sizeCode, hsnCode, gstRatePercent } = this.form.getRawValue();
    if (this.form.invalid || !sizeCode) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.cylinderTypeService
      .createCylinderType(sizeCode, { hsnCode, gstRatePercent: Number(gstRatePercent) })
      .subscribe({
        next: (created) => {
          this.submitting.set(false);
          this.notify.success(`Cylinder type "${created.name}" added.`);
          this.createDrawerVisible.set(false);
          this.resetCreateForm();
          this.reload();
        },
        error: () => this.submitting.set(false),
      });
  }

  protected openGstDrawer(cylinderType: CylinderTypeResponse): void {
    this.gstForm.reset({
      hsnCode: cylinderType.hsn_code ?? LPG_HSN_CODE,
      gstRatePercent:
        cylinderType.gst_rate_percent == null ? null : Number(cylinderType.gst_rate_percent),
    });
    this.gstTarget.set(cylinderType);
  }

  protected saveGst(): void {
    const target = this.gstTarget();
    if (!target || this.gstForm.invalid || this.submitting()) {
      this.gstForm.markAllAsTouched();
      return;
    }
    const { hsnCode, gstRatePercent } = this.gstForm.getRawValue();
    this.submitting.set(true);
    this.cylinderTypeService.classifyForGst(target.id, hsnCode, Number(gstRatePercent)).subscribe({
      next: () => {
        this.submitting.set(false);
        this.gstTarget.set(null);
        this.notify.success(`GST for "${target.name}" saved.`);
        this.reload();
      },
      error: () => this.submitting.set(false),
    });
  }

  protected toggleActive(cylinderType: CylinderTypeResponse): void {
    if (!cylinderType.is_active) {
      this.setActive(cylinderType, true);
      return;
    }
    this.confirmation.confirm({
      header: 'Deactivate cylinder type?',
      message: `"${cylinderType.name}" will no longer be offered in forms. You can activate it again later.`,
      acceptLabel: 'Deactivate',
      rejectLabel: 'Cancel',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => this.setActive(cylinderType, false),
    });
  }

  private setActive(cylinderType: CylinderTypeResponse, nextActive: boolean): void {
    this.cylinderTypeService.setActive(cylinderType.id, nextActive).subscribe({
      next: () => {
        this.notify.success(`"${cylinderType.name}" ${nextActive ? 'activated' : 'deactivated'}.`);
        this.reload();
      },
    });
  }
}
