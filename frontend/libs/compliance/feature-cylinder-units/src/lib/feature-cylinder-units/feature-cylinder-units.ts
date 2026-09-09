import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  DataGridComponent,
  type DataGridColumn,
  HasPermissionDirective,
  StatusChipCell,
  type ChipSeverity,
  FormFieldComponent,
  formatReportDate,
  toSentenceCase,
} from '@lpg/shared/ui';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { Dialog } from 'primeng/dialog';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { InputText } from 'primeng/inputtext';
import { DatePicker } from 'primeng/datepicker';
import { Select } from 'primeng/select';
import { Message } from 'primeng/message';
import { Tag } from 'primeng/tag';
import { MessageService } from 'primeng/api';
import {
  AdminCylinderTypeService,
  AdminWarehouseService,
  CylinderUnitService,
  CustomerService,
  DeliveryService,
  type AppError,
  type CylinderTypeResponse,
  type CylinderUnitResponse,
  type CustomerResponse,
  type VehicleResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'DUPLICATE_CYLINDER_SERIAL_NUMBER':
      return 'A cylinder unit with this serial number is already registered.';
    case 'DUPLICATE_CYLINDER_QR_CODE':
      return 'A cylinder unit with this QR / barcode is already registered.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    default:
      return 'Something went wrong. Please try again.';
  }
}

/** `dd-mm-yyyy`-picker value → `yyyy-mm-dd` API string, or `undefined`. */
function formatDateForApi(value: unknown): string | undefined {
  if (!value) return undefined;
  const d = new Date(value as string | number | Date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`;
}

/** The same condition-status vocabulary `InventoryLocation.CYLINDER_
 * STATUSES` establishes, plus a deliberately forked transition graph —
 * a single unit's real filled⇄empty cycle, distinct from
 * `InventoryLocation`'s own bulk-*balance* graph. Mirrors `domain.
 * compliance.cylinder_unit._CONDITION_TRANSITIONS` exactly; duplicated
 * client-side only for the UI's "which moves are offered" convenience —
 * the backend is the actual source of truth and will 422 on anything
 * this list gets wrong. */
const CONDITION_STATUSES = [
  'filled',
  'empty',
  'damaged',
  'leakage',
  'quarantine',
  'repair',
  'scrap',
] as const;

const CONDITION_TRANSITIONS: Record<string, readonly string[]> = {
  filled: ['empty', 'leakage'],
  empty: ['damaged', 'leakage'],
  damaged: ['quarantine'],
  leakage: ['quarantine'],
  quarantine: ['repair', 'scrap'],
  repair: ['empty'],
  scrap: [],
};

const CUSTODY_TYPES = ['warehouse', 'vehicle', 'customer', 'bottling_plant'] as const;

type ActiveAction = 'none' | 'test' | 'custody' | 'condition' | 'receive';

@Component({
  selector: 'lpg-feature-cylinder-units',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    FormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Drawer,
    DrawerA11yDirective,
    Dialog,
    Message,
    Select,
    Tag,
    DatePicker,
    DataGridComponent,
    FormFieldComponent,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-cylinder-units.html',
  styleUrl: './feature-cylinder-units.css',
})
export class FeatureCylinderUnits implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly cylinderUnitService = inject(CylinderUnitService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly messageService = inject(MessageService);

  private readonly deliveryService = inject(DeliveryService);
  private readonly customerService = inject(CustomerService);

  private static readonly CONDITION_SEVERITY: Record<string, ChipSeverity> = {
    filled: 'success',
    empty: 'secondary',
    damaged: 'warn',
    leakage: 'danger',
    quarantine: 'warn',
    repair: 'info',
    scrap: 'danger',
  };

  protected readonly dueStatusOptions = [
    { label: 'All units', value: 'all' },
    { label: 'Due ≤30d', value: 'due_soon' },
    { label: 'Overdue', value: 'overdue' },
  ];

  protected readonly conditionStatusOptions = CONDITION_STATUSES.map((s) => ({
    label: toSentenceCase(s),
    value: s,
  }));

  protected readonly custodyTypeOptions = CUSTODY_TYPES.map((c) => ({
    label: toSentenceCase(c),
    value: c,
  }));

  protected readonly toSentenceCase = toSentenceCase;
  protected readonly formatReportDate = formatReportDate;

  protected conditionSeverity(status: string): ChipSeverity {
    return FeatureCylinderUnits.CONDITION_SEVERITY[status] ?? 'secondary';
  }

  protected readonly units = signal<CylinderUnitResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly vehicles = signal<VehicleResponse[]>([]);
  protected readonly customers = signal<CustomerResponse[]>([]);
  protected readonly showMoveCustodyModal = signal(false);
  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly dueStatusFilter = signal<'all' | 'due_soon' | 'overdue'>('all');

  protected readonly cylinderTypeNameById = computed(() => {
    const map = new Map<string, string>();
    for (const t of this.cylinderTypes()) map.set(t.id, t.name);
    return map;
  });

  protected readonly warehouseNameById = computed(() => {
    const map = new Map<string, string>();
    for (const w of this.warehouses()) map.set(w.id, w.name);
    return map;
  });

  protected readonly vehicleNameById = computed(() => {
    const map = new Map<string, string>();
    for (const v of this.vehicles()) {
      map.set(v.id, `${v.registration_number}${v.model ? ' (' + v.model + ')' : ''}`);
    }
    return map;
  });

  protected readonly customerNameById = computed(() => {
    const map = new Map<string, string>();
    for (const c of this.customers()) {
      map.set(c.id, `${c.consumer_number} — ${c.full_name}`);
    }
    return map;
  });

  protected readonly warehouseOptions = computed(() =>
    this.warehouses().map((w) => ({ label: w.name, value: w.id }))
  );

  protected readonly vehicleOptions = computed(() =>
    this.vehicles().map((v) => ({
      label: `${v.registration_number}${v.model ? ' (' + v.model + ')' : ''}`,
      value: v.id,
    }))
  );

  protected readonly customerOptions = computed(() =>
    this.customers().map((c) => ({
      label: `${c.consumer_number} — ${c.full_name}`,
      value: c.id,
    }))
  );

  protected formatCustodyDisplay(custodyType: string, refId?: string | null): string {
    const typeLabel = toSentenceCase(custodyType);
    if (!refId) {
      return typeLabel;
    }
    if (custodyType === 'warehouse') {
      const name = this.warehouseNameById().get(refId);
      return name ? `Warehouse — ${name}` : `Warehouse (${refId.length > 8 ? refId.substring(0, 8) + '...' : refId})`;
    }
    if (custodyType === 'vehicle') {
      const name = this.vehicleNameById().get(refId);
      return name ? `Vehicle — ${name}` : `Vehicle (${refId.length > 8 ? refId.substring(0, 8) + '...' : refId})`;
    }
    if (custodyType === 'customer') {
      const name = this.customerNameById().get(refId);
      return name ? `Customer — ${name}` : `Customer (${refId.length > 8 ? refId.substring(0, 8) + '...' : refId})`;
    }
    return `${typeLabel} — ${refId}`;
  }

  protected readonly registerTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  protected readonly columns: DataGridColumn<CylinderUnitResponse>[] = [
    {
      field: 'serial_number',
      header: 'Serial',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.openDetails(row),
    },
    {
      field: 'qr_code',
      header: 'QR / Barcode',
      sortable: true,
      filterable: true,
    },
    {
      field: 'cylinder_type_id',
      header: 'Type',
      sortable: true,
      valueFormatter: (value) => this.cylinderTypeNameById().get(value as string) ?? (value as string),
    },
    {
      field: 'condition_status',
      header: 'Condition',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: FeatureCylinderUnits.CONDITION_SEVERITY },
    },
    {
      field: 'custody_type',
      header: 'Custody',
      sortable: true,
      valueFormatter: (value, row) => this.formatCustodyDisplay(value as string, row?.custody_ref_id),
    },
    {
      field: 'test_due_date',
      header: 'Test Due',
      sortable: true,
      valueFormatter: (value) => (value ? formatReportDate(value) : 'Never tested'),
    },
  ];

  // Register form
  protected readonly showRegisterModal = signal(false);
  protected readonly registerForm = this.fb.group({
    cylinder_type_id: ['', [Validators.required]],
    serial_number: ['', [Validators.required]],
    qr_code: [''],
    condition_status: ['empty', [Validators.required]],
    custody_type: ['warehouse', [Validators.required]],
    custody_ref_id: [''],
    manufacture_date: this.fb.control<Date | null>(null),
    owner_omc: [''],
  });

  protected readonly fieldMessages = {
    cylinder_type_id: { required: 'Select a cylinder type.' },
    serial_number: { required: 'Serial number is required.' },
    condition_status: { required: 'Select an initial condition.' },
    custody_type: { required: 'Select a custody type.' },
  };

  // Detail drawer
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedUnit = signal<CylinderUnitResponse | null>(null);
  protected readonly activeAction = signal<ActiveAction>('none');
  protected readonly saving = signal(false);
  protected readonly suggestedDueDate = signal<string | null>(null);

  protected readonly testForm = this.fb.group({
    tested_at: this.fb.control<Date | null>(new Date(), [Validators.required]),
    due_date: this.fb.control<Date | null>(null, [Validators.required]),
  });

  protected readonly custodyForm = this.fb.group({
    custody_type: ['warehouse', [Validators.required]],
    custody_ref_id: [''],
  });

  protected readonly conditionForm = this.fb.group({
    new_status: ['', [Validators.required]],
    reason: [''],
  });

  protected readonly receiveForm = this.fb.group({
    warehouse_id: ['', [Validators.required]],
  });

  protected readonly allowedNextConditions = computed(() => {
    const unit = this.selectedUnit();
    if (!unit) return [];
    const allowed = CONDITION_TRANSITIONS[unit.condition_status] ?? [];
    return this.conditionStatusOptions.filter((o) => allowed.includes(o.value));
  });

  ngOnInit(): void {
    this.loadCylinderTypes();
    this.loadWarehouses();
    this.loadVehicles();
    this.loadCustomers();
    this.loadUnits();

    this.custodyForm.controls.custody_type.valueChanges.subscribe((type) => {
      this.syncCustodyRefId(this.custodyForm, type);
    });
    this.registerForm.controls.custody_type.valueChanges.subscribe((type) => {
      this.syncCustodyRefId(this.registerForm, type);
    });
  }

  private syncCustodyRefId(form: typeof this.custodyForm | typeof this.registerForm, type: string): void {
    if (type === 'warehouse') {
      const wh = this.warehouses();
      form.controls.custody_ref_id.setValue(wh.length > 0 ? wh[0].id : '');
    } else if (type === 'vehicle') {
      const v = this.vehicles();
      form.controls.custody_ref_id.setValue(v.length > 0 ? v[0].id : '');
    } else if (type === 'customer') {
      const c = this.customers();
      form.controls.custody_ref_id.setValue(c.length > 0 ? c[0].id : '');
    } else {
      form.controls.custody_ref_id.setValue('');
    }
  }

  protected loadCylinderTypes(): void {
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (types) => this.cylinderTypes.set(types),
      error: () => this.errorMessage.set('Failed to load cylinder types.'),
    });
  }

  protected loadWarehouses(): void {
    this.warehouseService.listWarehouses().subscribe({
      next: (warehouses) => {
        this.warehouses.set(warehouses);
        if (this.registerForm.controls.custody_type.value === 'warehouse' && !this.registerForm.controls.custody_ref_id.value && warehouses.length > 0) {
          this.registerForm.controls.custody_ref_id.setValue(warehouses[0].id);
        }
      },
      error: () => this.errorMessage.set('Failed to load warehouses.'),
    });
  }

  protected loadVehicles(): void {
    this.deliveryService.listVehicles(0, 200).subscribe({
      next: (page) => this.vehicles.set(page.items),
      error: () => {},
    });
  }

  protected loadCustomers(): void {
    this.customerService.list(0, 200).subscribe({
      next: (page) => this.customers.set(page.items),
      error: () => {},
    });
  }

  protected loadUnits(): void {
    this.loading.set(true);
    const filter = this.dueStatusFilter();
    this.cylinderUnitService
      .listCylinderUnits({ dueStatus: filter === 'all' ? undefined : filter, limit: 200 })
      .subscribe({
        next: (page) => {
          this.units.set(page.items);
          this.loading.set(false);
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected onDueStatusFilterChange(value: 'all' | 'due_soon' | 'overdue'): void {
    this.dueStatusFilter.set(value);
    this.loadUnits();
  }

  protected openRegisterModal(): void {
    this.registerForm.reset({
      cylinder_type_id: this.cylinderTypes().length > 0 ? this.cylinderTypes()[0].id : '',
      serial_number: '',
      qr_code: '',
      condition_status: 'empty',
      custody_type: 'warehouse',
      custody_ref_id: '',
      manufacture_date: null,
      owner_omc: '',
    });
    this.showRegisterModal.set(true);
  }

  protected onSubmitRegister(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }
    const val = this.registerForm.getRawValue();
    this.loading.set(true);
    this.cylinderUnitService
      .registerCylinderUnit({
        cylinder_type_id: val.cylinder_type_id,
        serial_number: val.serial_number,
        qr_code: val.qr_code.trim() ? val.qr_code.trim() : undefined,
        condition_status: val.condition_status,
        custody_type: val.custody_type,
        custody_ref_id: val.custody_ref_id || null,
        manufacture_date: formatDateForApi(val.manufacture_date) ?? null,
        owner_omc: val.owner_omc || null,
      })
      .subscribe({
        next: () => {
          this.showRegisterModal.set(false);
          this.loadUnits();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
          this.messageService.add({
            severity: 'error',
            summary: 'Error',
            detail: errorMessageFor(err),
          });
        },
      });
  }

  protected openDetails(unit: CylinderUnitResponse): void {
    this.selectedUnit.set(unit);
    this.activeAction.set('none');
    this.suggestedDueDate.set(null);
    this.showDetailDrawer.set(true);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
    this.activeAction.set('none');
  }

  protected openMoveCustody(unit?: CylinderUnitResponse): void {
    const target = unit ?? this.selectedUnit();
    if (!target) return;
    this.selectedUnit.set(target);
    this.custodyForm.reset({
      custody_type: target.custody_type,
      custody_ref_id: target.custody_ref_id ?? '',
    });
    if (!this.custodyForm.controls.custody_ref_id.value) {
      this.syncCustodyRefId(this.custodyForm, target.custody_type);
    }
    this.showMoveCustodyModal.set(true);
  }

  protected closeMoveCustody(): void {
    this.showMoveCustodyModal.set(false);
  }

  protected openMoveCustodyFromLookup(): void {
    const result = this.lookupResult();
    if (!result) return;
    this.showLookupModal.set(false);
    this.openMoveCustody(result);
  }

  protected startAction(action: ActiveAction): void {
    const unit = this.selectedUnit();
    if (!unit) return;
    if (action === 'test') {
      this.testForm.reset({ tested_at: new Date(), due_date: null });
      this.suggestedDueDate.set(null);
    } else if (action === 'custody') {
      this.openMoveCustody();
      return;
    } else if (action === 'condition') {
      this.conditionForm.reset({ new_status: '', reason: '' });
    } else if (action === 'receive') {
      this.receiveForm.reset({
        warehouse_id: this.warehouses().length > 0 ? this.warehouses()[0].id : '',
      });
    }
    this.activeAction.set(action);
  }

  protected cancelAction(): void {
    this.activeAction.set('none');
  }

  protected onTestedAtChange(): void {
    const testedAt = this.testForm.controls.tested_at.value;
    const isoTestedAt = formatDateForApi(testedAt);
    if (!isoTestedAt) {
      this.suggestedDueDate.set(null);
      return;
    }
    this.cylinderUnitService.suggestTestDueDate(isoTestedAt).subscribe({
      next: (res) => this.suggestedDueDate.set(res.suggested_due_date),
      error: () => this.suggestedDueDate.set(null),
    });
  }

  protected applySuggestedDueDate(): void {
    const suggestion = this.suggestedDueDate();
    if (!suggestion) return;
    this.testForm.controls.due_date.setValue(new Date(suggestion));
  }

  protected saveTest(): void {
    const unit = this.selectedUnit();
    if (!unit || this.testForm.invalid) return;
    const val = this.testForm.getRawValue();
    const testedAt = formatDateForApi(val.tested_at);
    const dueDate = formatDateForApi(val.due_date);
    if (!testedAt || !dueDate) return;

    this.saving.set(true);
    this.cylinderUnitService.recordStatutoryTest(unit.id, { tested_at: testedAt, due_date: dueDate }).subscribe({
      next: (updated) => {
        this.selectedUnit.set(updated);
        this.activeAction.set('none');
        this.saving.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Test recorded.' });
        this.loadUnits();
      },
      error: (err) => {
        this.saving.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
      },
    });
  }

  protected saveCustody(): void {
    const unit = this.selectedUnit();
    if (!unit || this.custodyForm.invalid) return;
    const val = this.custodyForm.getRawValue();
    this.saving.set(true);
    this.cylinderUnitService
      .moveCustody(unit.id, {
        custody_type: val.custody_type,
        custody_ref_id: val.custody_type === 'bottling_plant' ? null : val.custody_ref_id || null,
      })
      .subscribe({
        next: (updated) => {
          this.selectedUnit.set(updated);
          this.activeAction.set('none');
          this.showMoveCustodyModal.set(false);
          this.saving.set(false);
          this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Custody updated.' });
          this.loadUnits();
        },
        error: (err) => {
          this.saving.set(false);
          this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
        },
      });
  }

  protected saveCondition(): void {
    const unit = this.selectedUnit();
    if (!unit || this.conditionForm.invalid) return;
    const val = this.conditionForm.getRawValue();
    this.saving.set(true);
    this.cylinderUnitService
      .changeConditionStatus(unit.id, { new_status: val.new_status, reason: val.reason || null })
      .subscribe({
        next: (updated) => {
          this.selectedUnit.set(updated);
          this.activeAction.set('none');
          this.saving.set(false);
          this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Condition updated.' });
          this.loadUnits();
        },
        error: (err) => {
          this.saving.set(false);
          this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
        },
      });
  }

  protected saveReceive(): void {
    const unit = this.selectedUnit();
    if (!unit || this.receiveForm.invalid) return;
    const val = this.receiveForm.getRawValue();
    this.saving.set(true);
    this.cylinderUnitService.receiveCylinderUnit(unit.id, val.warehouse_id).subscribe({
      next: (updated) => {
        this.selectedUnit.set(updated);
        this.activeAction.set('none');
        this.saving.set(false);
        this.messageService.add({ severity: 'success', summary: 'Received', detail: 'Cylinder received into stock.' });
        this.loadUnits();
      },
      error: (err) => {
        this.saving.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
      },
    });
  }

  protected retire(): void {
    const unit = this.selectedUnit();
    if (!unit) return;
    this.saving.set(true);
    this.cylinderUnitService.retireCylinderUnit(unit.id).subscribe({
      next: (updated) => {
        this.selectedUnit.set(updated);
        this.saving.set(false);
        this.messageService.add({ severity: 'success', summary: 'Retired', detail: 'Cylinder unit retired.' });
        this.loadUnits();
      },
      error: (err) => {
        this.saving.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(err) });
      },
    });
  }

  // Printing & QR Lookup
  protected readonly printingLabel = signal(false);
  protected readonly showLookupModal = signal(false);
  protected readonly lookupCode = signal('');
  protected readonly lookupSearching = signal(false);
  protected readonly lookupResult = signal<CylinderUnitResponse | null>(null);
  protected readonly lookupNotFound = signal(false);

  protected printLabel(unitId: string): void {
    this.printingLabel.set(true);
    this.cylinderUnitService.printCylinderUnitLabel(unitId).subscribe({
      next: (blob) => {
        this.printingLabel.set(false);
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
        this.messageService.add({
          severity: 'success',
          summary: 'Label Ready',
          detail: 'Thermal sticker opened for printing.',
        });
      },
      error: (err) => {
        this.printingLabel.set(false);
        this.messageService.add({
          severity: 'error',
          summary: 'Print Failed',
          detail: errorMessageFor(err),
        });
      },
    });
  }

  protected openLookupModal(): void {
    this.lookupCode.set('');
    this.lookupResult.set(null);
    this.lookupNotFound.set(false);
    this.showLookupModal.set(true);
  }

  protected performLookup(): void {
    const code = this.lookupCode().trim();
    if (!code) return;
    this.lookupSearching.set(true);
    this.lookupNotFound.set(false);
    this.lookupResult.set(null);
    this.cylinderUnitService.lookupCylinderUnit(code).subscribe({
      next: (unit) => {
        this.lookupResult.set(unit);
        this.lookupSearching.set(false);
      },
      error: () => {
        this.lookupSearching.set(false);
        this.lookupNotFound.set(true);
      },
    });
  }

  protected openDetailsFromLookup(): void {
    const result = this.lookupResult();
    if (!result) return;
    this.showLookupModal.set(false);
    this.openDetails(result);
  }
}
