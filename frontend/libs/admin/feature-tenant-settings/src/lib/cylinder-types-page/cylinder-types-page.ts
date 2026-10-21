import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
  viewChild,
  computed,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import {
  AdminCylinderTypeService,
  NotifyService,
  type CylinderTypeResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, FormFieldComponent } from '@lpg/shared/ui';

/** AG Grid renders a boolean-valued column with its own checkbox cell by
 * default, ignoring `valueFormatter` (same issue fixed for Platform
 * Flags' "Default" column and Linked Devices' "Status" column) — this
 * swaps that for plain "Active"/"Inactive" text. */
/** HSN for liquefied petroleum gas — every cylinder type an agency sells. */
const LPG_HSN_CODE = '27111900';
const HSN_PATTERN = /^(?:[0-9]{4}|[0-9]{6}|[0-9]{8})$/;

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

/** Cylinder type list + create drawer â€” `tenant:configure`. */
@Component({
  selector: 'lpg-cylinder-types-page',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    DataGridComponent,
    FormFieldComponent,
    Drawer,
    DrawerA11yDirective,
    IconField,
    InputIcon,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <div class="page-header__text">
            <h1 class="page-title">Cylinder Types</h1>
            <p class="page-subtitle">Define LPG cylinder sizes, weights and GST.</p>
          </div>
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

      @if (cylinderTypes().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
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
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary" type="button" (click)="exportCsv()">
              <i class="pi pi-file-excel"></i><span>Export CSV</span>
            </button>
            <button pButton (click)="openCreateDrawer()">
              <i class="pi pi-plus"></i><span>Add Cylinder Type</span>
            </button>
          </div>
        </div>
      }

      @if (!loading() && cylinderTypes().length === 0) {
        <div class="empty-state">
          <i class="pi pi-box empty-state__icon"></i>
          <p class="empty-state__title">No cylinder types found</p>
          <p class="empty-state__description">Get started by defining your first cylinder size.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Add Cylinder Type</span>
          </button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="cylinderTypes()"
            [columns]="columns"
            [loading]="loading()"
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
            <p class="page-lede">Define a new LPG cylinder type by name and weight.</p>

            <lpg-form-field
              label="Name"
              for="cylinder-name"
              [control]="form.controls.name"
              [messages]="{ required: 'Cylinder type name is required.' }"
            >
              <input
                pInputText
                id="cylinder-name"
                type="text"
                formControlName="name"
                placeholder="e.g. 14.2 kg Domestic"
                [fluid]="true"
              />
            </lpg-form-field>

            <lpg-form-field
              label="Weight (kg)"
              for="cylinder-weight"
              [control]="form.controls.weightKg"
              [messages]="{
                required: 'Weight is required.',
                min: 'Weight must be greater than 0.',
              }"
            >
              <input
                pInputText
                id="cylinder-weight"
                type="number"
                step="0.01"
                formControlName="weightKg"
                placeholder="e.g. 14.2"
                [fluid]="true"
              />
            </lpg-form-field>

            <div class="gst-fields">
              <lpg-form-field
                label="HSN code"
                for="cylinder-hsn"
                [control]="form.controls.hsnCode"
                [messages]="{
                  required: 'HSN code is required.',
                  pattern: 'HSN is 4, 6 or 8 digits.',
                }"
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
                hint="LPG: 5% for domestic, 18% for commercial cylinders."
                [messages]="{
                  required: 'GST rate is required.',
                  min: 'Rate cannot be negative.',
                  max: 'The highest GST rate is 28%.',
                }"
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
            <button pButton type="submit" [disabled]="submitting() || form.invalid">
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
              [messages]="{
                required: 'HSN code is required.',
                pattern: 'HSN is 4, 6 or 8 digits.',
              }"
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
              hint="LPG: 5% for domestic, 18% for commercial cylinders."
              [messages]="{
                required: 'GST rate is required.',
                min: 'Rate cannot be negative.',
                max: 'The highest GST rate is 28%.',
              }"
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

  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);
  protected readonly gstTarget = signal<CylinderTypeResponse | null>(null);
  protected readonly unclassifiedCount = computed(
    () => this.cylinderTypes().filter((c) => c.is_active && c.gst_rate_percent == null).length,
  );

  protected readonly columns: DataGridColumn<CylinderTypeResponse>[] = [
    { field: 'name', header: 'Name', sortable: true, filterable: true },
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
    {
      field: 'gst_action',
      header: '',
      valueFormatter: () => 'Set GST',
      onLinkClick: (row) => this.openGstDrawer(row),
    },
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

  protected readonly form = this.formBuilder.group({
    name: ['', [Validators.required]],
    weightKg: [0, [Validators.required, Validators.min(0.01)]],
    hsnCode: [LPG_HSN_CODE, [Validators.required, Validators.pattern(HSN_PATTERN)]],
    gstRatePercent: [
      null as number | null,
      [Validators.required, Validators.min(0), Validators.max(28)],
    ],
  });

  protected readonly gstForm = this.formBuilder.group({
    hsnCode: [LPG_HSN_CODE, [Validators.required, Validators.pattern(HSN_PATTERN)]],
    gstRatePercent: [
      null as number | null,
      [Validators.required, Validators.min(0), Validators.max(28)],
    ],
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (cylinderTypes) => {
        this.cylinderTypes.set(cylinderTypes);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected openCreateDrawer(): void {
    this.form.reset({ weightKg: 0, hsnCode: LPG_HSN_CODE, gstRatePercent: null });
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
    const { name, weightKg, hsnCode, gstRatePercent } = this.form.getRawValue();

    this.cylinderTypeService
      .createCylinderType(name, weightKg, { hsnCode, gstRatePercent: Number(gstRatePercent) })
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.notify.success(`Cylinder type "${name}" added.`);
          this.createDrawerVisible.set(false);
          this.form.reset({ weightKg: 0, hsnCode: LPG_HSN_CODE, gstRatePercent: null });
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
    const nextActive = !cylinderType.is_active;
    this.cylinderTypeService.setActive(cylinderType.id, nextActive).subscribe({
      next: () => {
        this.notify.success(`"${cylinderType.name}" ${nextActive ? 'activated' : 'deactivated'}.`);
        this.reload();
      },
    });
  }
}
