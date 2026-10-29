import { HeaderTitlePortalDirective, PageActionsDirective } from '@lpg/shared/ui/app-shell';
import { HasPermissionDirective } from '@lpg/shared/ui';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import {
  FormsModule,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { DatePicker } from 'primeng/datepicker';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { InputNumber } from 'primeng/inputnumber';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Textarea } from 'primeng/textarea';
import {
  AdminCylinderTypeService,
  AdminWarehouseService,
  DeliveryService,
  InventoryService,
  NotifyService,
  WeighmentService,
  errorMessageFor as sharedErrorMessageFor,
  isAppError,
  type CylinderTypeResponse,
  type GoodsReceiptResponse,
  type InventoryBalanceLine,
  type InventoryBalanceResponse,
  type InventoryLocationType,
  type InventoryTransactionResponse,
  type OmcReturnRequest,
  type ReconciliationRecordResponse,
  type StatusTransitionsResponse,
  type StockRegisterLineResponse,
  type ReorderPolicyResponse,
  type ReorderSignalResponse,
  type ScaleResponse,
  type VehicleResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';
import {
  DataGridComponent,
  type DataGridColumn,
  FormFieldComponent,
  PageHeaderComponent,
  StatusChipCell,
  toSentenceCase,
} from '@lpg/shared/ui';

const CYLINDER_STATUSES = [
  'filled',
  'empty',
  'damaged',
  'leakage',
  'quarantine',
  'repair',
  'scrap',
] as const;

/** Oil marketing companies a GRN comes from / empties go back to — the
 * same closed set the API validates. */
const OMC_OPTIONS = [
  { label: 'IOCL (Indane)', value: 'iocl' },
  { label: 'BPCL (Bharatgas)', value: 'bpcl' },
  { label: 'HPCL (HP Gas)', value: 'hpcl' },
  { label: 'Other', value: 'other' },
] as const;
type OmcCode = (typeof OMC_OPTIONS)[number]['value'];

/** Statuses that can go back to the OMC (empties and defectives). */
const OMC_RETURNABLE_STATUSES = ['empty', 'damaged', 'leakage', 'quarantine'] as const;

/** How many days the stock register shows by default. */
const STOCK_REGISTER_DEFAULT_DAYS = 7;

type TransitionKind = keyof StatusTransitionsResponse;
/** A cylinder status as the API types it; form values come from these options. */
type CylinderStatus = (typeof CYLINDER_STATUSES)[number];

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'INSUFFICIENT_STOCK':
      return 'Not enough stock available for that quantity.';
    case 'INVALID_STATUS_TRANSITION':
      return 'That status change is not permitted.';
    case 'SELF_APPROVAL_NOT_ALLOWED':
      return 'You recorded this count, so someone else has to approve it.';
    case 'RECONCILIATION_ALREADY_DECIDED':
      return 'This count has already been approved or rejected.';
    default:
      return sharedErrorMessageFor(error);
  }
}

/** Local calendar date → `yyyy-mm-dd`. */
function toIsoDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

@Component({
  selector: 'lpg-feature-inventory',
  standalone: true,
  imports: [
    PageActionsDirective,
    PageHeaderComponent,
    HeaderTitlePortalDirective,
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    InputNumber,
    Textarea,
    Drawer,
    DrawerA11yDirective,
    DatePicker,
    Message,
    Select,
    DataGridComponent,
    FormFieldComponent,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-inventory.html',
  styleUrl: './feature-inventory.css',
})
export class FeatureInventory implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly inventoryService = inject(InventoryService);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly deliveryService = inject(DeliveryService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly weighmentService = inject(WeighmentService);
  private readonly notify = inject(NotifyService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute, { optional: true });

  protected readonly selectedCylinderTypeId = signal<string | null>(null);

  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly vehicles = signal<VehicleResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly scales = signal<ScaleResponse[]>([]);

  protected readonly statusOptions = CYLINDER_STATUSES.map((s) => ({
    label: toSentenceCase(s),
    value: s,
  }));
  protected readonly omcOptions = [...OMC_OPTIONS];
  protected readonly omcReturnStatusOptions = OMC_RETURNABLE_STATUSES.map((s) => ({
    label: toSentenceCase(s),
    value: s,
  }));

  /** Allowed status moves, from the API (the domain's own rule, DA-17). */
  private readonly transitions = signal<StatusTransitionsResponse | null>(null);

  /**
   * Validator-key → message, shared across the six inventory-operation forms
   * (they reuse the same field names). `lpg-form-field` falls back to a
   * generic message for any key not listed.
   */
  protected readonly fieldMessages = {
    cylinder_type_id: { required: 'Select a cylinder type.' },
    quantity: { required: 'Enter a quantity.', min: 'Quantity must be at least 1.' },
    quantity_received: { required: 'Enter a quantity.', min: 'Quantity must be at least 1.' },
    actual_quantity: { required: 'Enter the counted quantity.', min: 'Cannot be negative.' },
    warehouse_id: { required: 'Select a godown.' },
    vehicle_id: { required: 'Select a vehicle.' },
    status: { required: 'Select a status.' },
    from_status: { required: 'Select the current status.' },
    to_status: { required: 'Select the target status.' },
    mode: { required: 'Choose an action.' },
    reason: { required: 'A reason is required.', minlength: 'Give a little more detail.' },
    scale_id: { required: 'Select a certified scale.' },
    cylinders_checked: {
      required: 'Enter how many cylinders were weighed.',
      min: 'Must be at least 1.',
      max: 'Cannot exceed the batch size.',
    },
    underweight_cylinder_count: {
      required: 'Enter the underweight count (0 if none).',
      min: 'Cannot be negative.',
    },
    destination_omc: { required: 'Choose the OMC the cylinders go back to.' },
    reorder_point: { required: 'Enter a reorder point.', min: 'Cannot be negative.' },
    safety_stock: { required: 'Enter a safety stock level.', min: 'Cannot be negative.' },
  };

  protected readonly locationType = signal<InventoryLocationType>('warehouse');
  protected readonly locationRefId = signal<string | null>(null);
  protected readonly balance = signal<InventoryBalanceResponse | null>(null);
  protected readonly transactions = signal<InventoryTransactionResponse[]>([]);

  protected readonly loading = signal(false);
  /** Page-level load failures (balance, history, register). */
  protected readonly errorMessage = signal<string | null>(null);
  /** The open drawer's own failure — shown inside it, once (DA-16). Cleared
   * whenever a drawer opens. */
  protected readonly drawerError = signal<string | null>(null);

  protected readonly cylinderTypeNameById = computed(() => {
    const map = new Map<string, string>();
    for (const ct of this.cylinderTypes()) map.set(ct.id, ct.name);
    return map;
  });

  protected readonly locationOptions = computed(() =>
    this.locationType() === 'warehouse'
      ? this.warehouses().map((w) => ({ label: w.name, value: w.id }))
      : this.vehicles().map((v) => ({ label: v.registration_number, value: v.id })),
  );

  /** Certified scales at the currently-selected warehouse — `/scales` has no
   * server-side warehouse filter (D24 Weighment §API), so this narrows
   * client-side, same as `activeScalesForWarehouse` in the dispatch load-out
   * screen. */
  protected readonly activeScalesForWarehouse = computed(() =>
    this.scales().filter((s) => s.status === 'active' && s.warehouse_id === this.locationRefId()),
  );

  // Modal visibility
  protected readonly showGrnModal = signal(false);
  protected readonly showTransferModal = signal(false);
  protected readonly showDeliveryCollectionModal = signal(false);
  protected readonly showStatusChangeModal = signal(false);
  protected readonly showAdjustModal = signal(false);
  protected readonly showReconcileModal = signal(false);
  protected readonly showOmcReturnModal = signal(false);
  protected readonly showRejectModal = signal(false);

  // PrimeNG's Dialog/Drawer has no built-in "return focus to trigger"
  // behaviour — matches `apps/dashboard/src/app/home/home.ts`'s pattern.
  protected readonly grnTrigger = viewChild<ElementRef<HTMLButtonElement>>('grnTriggerEl');
  protected readonly transferTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('transferTriggerEl');
  protected readonly deliveryCollectionTrigger = viewChild<ElementRef<HTMLButtonElement>>(
    'deliveryCollectionTriggerEl',
  );
  protected readonly statusChangeTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('statusChangeTriggerEl');
  protected readonly adjustTrigger = viewChild<ElementRef<HTMLButtonElement>>('adjustTriggerEl');
  protected readonly reconcileTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('reconcileTriggerEl');
  protected readonly omcReturnTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('omcReturnTriggerEl');

  protected readonly balanceColumns: DataGridColumn<InventoryBalanceLine>[] = [
    {
      field: 'cylinder_type_id',
      header: 'Cylinder Type',
      sortable: true,
      valueFormatter: (value) =>
        this.cylinderTypeNameById().get(value as string) ?? (value as string),
    },
    { field: 'status', header: 'Status', sortable: true, cellRenderer: StatusChipCell },
    { field: 'quantity', header: 'Quantity', sortable: true, numeric: true, width: 140 },
  ];

  protected readonly transactionColumns: DataGridColumn<InventoryTransactionResponse>[] = [
    { field: 'transaction_type', header: 'Type', sortable: true, cellRenderer: StatusChipCell },
    {
      field: 'cylinder_type_id',
      header: 'Cylinder Type',
      valueFormatter: (value) =>
        this.cylinderTypeNameById().get(value as string) ?? (value as string),
    },
    { field: 'from_status', header: 'From', cellRenderer: StatusChipCell },
    { field: 'to_status', header: 'To', cellRenderer: StatusChipCell },
    { field: 'quantity', header: 'Qty', numeric: true },
    {
      field: 'performed_at',
      header: 'When',
      sortable: true,
      valueFormatter: (value) => new Date(value as string).toLocaleString(),
    },
  ];

  protected readonly grnForm = this.fb.group({
    cylinder_type_id: ['', [Validators.required]],
    quantity_received: [1, [Validators.required, Validators.min(1)]],
    source_omc: ['' as OmcCode | ''],
    challan_number: ['', [Validators.maxLength(50)]],
    invoice_number: ['', [Validators.maxLength(50)]],
    truck_number: ['', [Validators.maxLength(20)]],
  });

  /** Empties (and defectives) going back to the OMC on its truck (DA-34). */
  protected readonly omcReturnForm = this.fb.group({
    destination_omc: ['' as OmcCode | '', [Validators.required]],
    cylinder_type_id: ['', [Validators.required]],
    status: ['empty' as (typeof OMC_RETURNABLE_STATUSES)[number], [Validators.required]],
    quantity: [1, [Validators.required, Validators.min(1)]],
    challan_number: ['', [Validators.maxLength(50)]],
    truck_number: ['', [Validators.maxLength(20)]],
  });

  /** MDG 2022 cl. 1.2(iv) — 10% goods-receipt sample. Surfaced as a second
   * step inside the same "Receive Goods" drawer once the GRN itself is
   * saved, since the physical weighing happens after the truck is logged
   * in, not atomically with it (`foamy-forging-sparrow.md`'s own framing).
   * Non-blocking — skipping it leaves the GRN as recorded either way. */
  protected readonly lastGrn = signal<GoodsReceiptResponse | null>(null);
  protected readonly weighmentForm = this.fb.group({
    scale_id: ['', [Validators.required]],
    cylinders_checked: [1, [Validators.required, Validators.min(1)]],
    underweight_cylinder_count: [0, [Validators.required, Validators.min(0)]],
  });

  protected readonly transferForm = this.fb.group({
    warehouse_id: ['', [Validators.required]],
    vehicle_id: ['', [Validators.required]],
    cylinder_type_id: ['', [Validators.required]],
    status: ['filled', [Validators.required]],
    quantity: [1, [Validators.required, Validators.min(1)]],
  });

  protected readonly deliveryCollectionForm = this.fb.group({
    mode: ['delivery' as 'delivery' | 'collection', [Validators.required]],
    cylinder_type_id: ['', [Validators.required]],
    quantity: [1, [Validators.required, Validators.min(1)]],
  });

  protected readonly statusChangeForm = this.fb.group({
    cylinder_type_id: ['', [Validators.required]],
    from_status: ['filled', [Validators.required]],
    to_status: ['leakage', [Validators.required]],
    quantity: [1, [Validators.required, Validators.min(1)]],
  });

  protected readonly adjustForm = this.fb.group({
    cylinder_type_id: ['', [Validators.required]],
    from_status: ['filled', [Validators.required]],
    to_status: ['leakage', [Validators.required]],
    quantity: [1, [Validators.required, Validators.min(1)]],
    reason: ['', [Validators.required, Validators.minLength(3)]],
  });

  protected readonly reconcileForm = this.fb.group({
    cylinder_type_id: ['', [Validators.required]],
    status: ['filled', [Validators.required]],
    actual_quantity: [0, [Validators.required, Validators.min(0)]],
  });

  protected readonly lastReconciliationRecordId = signal<string | null>(null);

  /** Counts recorded here and waiting for a second person's decision (DA-04). */
  protected readonly pendingCounts = signal<ReconciliationRecordResponse[]>([]);
  protected readonly countsError = signal<string | null>(null);
  protected readonly rejectingCount = signal<ReconciliationRecordResponse | null>(null);
  protected readonly rejectForm = this.fb.group({
    reason: ['', [Validators.required, Validators.minLength(3)]],
  });

  // Stock register (DA-34): opening / receipts / issues / closing per day.
  protected readonly registerFrom = signal<Date>(this.daysAgo(STOCK_REGISTER_DEFAULT_DAYS - 1));
  protected readonly registerTo = signal<Date>(new Date());
  protected readonly registerLines = signal<StockRegisterLineResponse[]>([]);
  protected readonly registerLoading = signal(false);
  protected readonly registerColumns: DataGridColumn<StockRegisterLineResponse>[] = [
    { field: 'date', header: 'Date', sortable: true, width: 130 },
    {
      field: 'cylinder_type_id',
      header: 'Cylinder Type',
      sortable: true,
      filterable: true,
      valueFormatter: (value) =>
        this.cylinderTypeNameById().get(value as string) ?? (value as string),
    },
    { field: 'status', header: 'Status', sortable: true, cellRenderer: StatusChipCell },
    { field: 'opening', header: 'Opening', numeric: true, width: 120 },
    { field: 'receipts', header: 'Receipts', numeric: true, width: 120 },
    { field: 'issues', header: 'Issues', numeric: true, width: 120 },
    { field: 'closing', header: 'Closing', numeric: true, width: 120 },
  ];

  // ---------------------------------------------------------------------------
  // Reorder policy (AI Operational Intelligence, Horizon 1 Stage 4)
  // ---------------------------------------------------------------------------

  protected readonly reorderPolicies = signal<ReorderPolicyResponse[]>([]);
  protected readonly reorderSignals = signal<ReorderSignalResponse[]>([]);
  protected readonly showReorderPolicyModal = signal(false);
  protected readonly reorderPolicyTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('reorderPolicyTriggerEl');

  protected readonly warehouseNameById = computed(() => {
    const map = new Map<string, string>();
    for (const w of this.warehouses()) map.set(w.id, w.name);
    return map;
  });

  protected readonly reorderPolicyForm = this.fb.group({
    warehouse_id: ['', [Validators.required]],
    cylinder_type_id: ['', [Validators.required]],
    reorder_point: [10, [Validators.required, Validators.min(0)]],
    safety_stock: [0, [Validators.required, Validators.min(0)]],
  });

  protected readonly reorderPolicyColumns: DataGridColumn<ReorderPolicyResponse>[] = [
    {
      field: 'location_ref_id',
      header: 'Godown',
      sortable: true,
      valueFormatter: (value) => this.warehouseNameById().get(value as string) ?? (value as string),
    },
    {
      field: 'cylinder_type_id',
      header: 'Cylinder Type',
      sortable: true,
      valueFormatter: (value) =>
        this.cylinderTypeNameById().get(value as string) ?? (value as string),
    },
    { field: 'reorder_point', header: 'Reorder Point', numeric: true },
    { field: 'safety_stock', header: 'Safety Stock', numeric: true },
  ];

  constructor() {
    // Keep each "To" picker on a move the domain allows from the chosen
    // "From" status (DA-17).
    this.keepTargetAllowed(this.statusChangeForm, 'status_change');
    this.keepTargetAllowed(this.adjustForm, 'adjustment');
  }

  ngOnInit(): void {
    this.inventoryService.getStatusTransitions().subscribe({
      next: (t) => {
        this.transitions.set(t);
        this.statusChangeForm.controls.to_status.setValue(
          this.firstTarget('status_change', this.statusChangeForm.controls.from_status.value),
        );
        this.adjustForm.controls.to_status.setValue(
          this.firstTarget('adjustment', this.adjustForm.controls.from_status.value),
        );
      },
    });
    this.warehouseService.listWarehouses().subscribe({ next: (w) => this.warehouses.set(w) });
    this.deliveryService.listVehicles(0, 200).subscribe({
      next: (page) => this.vehicles.set(page.items),
    });
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (ct) => this.cylinderTypes.set(ct),
    });
    this.weighmentService.listScales({ status: 'active', limit: 200 }).subscribe({
      next: (res) => this.scales.set(res.items),
    });
    this.loadReorderPolicies();
    this.loadReorderSignals();

    this.route?.queryParams.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const type = params['type'] as InventoryLocationType | undefined;
      const id = params['id'] as string | undefined;
      const cylinderTypeId = params['cylinder_type_id'] as string | undefined;

      if (type === 'warehouse' || type === 'vehicle') {
        this.locationType.set(type);
      }
      if (id) {
        this.locationRefId.set(id);
        this.reload();
      }
      if (cylinderTypeId) {
        this.selectedCylinderTypeId.set(cylinderTypeId);
        this.reconcileForm.controls.cylinder_type_id.setValue(cylinderTypeId);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Allowed status moves (DA-17)
  // ---------------------------------------------------------------------------

  /** "From" statuses with at least one allowed move. */
  protected fromStatusOptions(kind: TransitionKind): { label: string; value: string }[] {
    const map = this.transitions()?.[kind];
    if (!map) return this.statusOptions;
    return this.statusOptions.filter((o) => (map[o.value] ?? []).length > 0);
  }

  /** The moves the domain allows from `from`. */
  protected toStatusOptions(
    kind: TransitionKind,
    from: string,
  ): { label: string; value: string }[] {
    const targets = this.transitions()?.[kind]?.[from] ?? [];
    return targets.map((t) => ({ label: toSentenceCase(t), value: t }));
  }

  private firstTarget(kind: TransitionKind, from: string): string {
    return this.transitions()?.[kind]?.[from]?.[0] ?? '';
  }

  private keepTargetAllowed(
    form: typeof this.statusChangeForm | typeof this.adjustForm,
    kind: TransitionKind,
  ): void {
    form.controls.from_status.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((from) => {
        const allowed = this.transitions()?.[kind]?.[from] ?? [];
        if (!allowed.includes(form.controls.to_status.value)) {
          form.controls.to_status.setValue(allowed[0] ?? '');
        }
      });
  }

  protected onLocationTypeChange(value: InventoryLocationType): void {
    this.locationType.set(value);
    this.locationRefId.set(null);
    this.balance.set(null);
    this.transactions.set([]);
    this.pendingCounts.set([]);
    this.registerLines.set([]);
  }

  protected onLocationRefChange(value: string): void {
    this.locationRefId.set(value);
    this.errorMessage.set(null);
    this.reload();
  }

  /** Re-reads everything shown for the selected location. */
  reload(): void {
    this.loadBalance();
    this.loadTransactions();
    this.loadPendingCounts();
    this.loadStockRegister();
  }

  protected loadBalance(): void {
    const refId = this.locationRefId();
    if (!refId) return;
    this.loading.set(true);
    this.inventoryService.getBalance(this.locationType(), refId).subscribe({
      next: (res) => {
        this.balance.set(res);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected loadTransactions(): void {
    const refId = this.locationRefId();
    if (!refId) return;
    this.inventoryService.listTransactions(this.locationType(), refId, undefined, 100).subscribe({
      next: (page) => {
        this.transactions.set(page.items);
      },
      error: (err) => this.errorMessage.set(errorMessageFor(err)),
    });
  }

  private refreshAfterMutation(message: string): void {
    this.loading.set(false);
    this.notify.success(message);
    this.reload();
  }

  /** A drawer's request failed: say why inside that drawer, once. */
  private failInDrawer(err: unknown): void {
    this.drawerError.set(errorMessageFor(err));
    this.loading.set(false);
  }

  private daysAgo(days: number): Date {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return d;
  }

  // ---------------------------------------------------------------------------
  // Goods Receipt (warehouse-only)
  // ---------------------------------------------------------------------------

  protected openGrnModal(): void {
    this.grnForm.reset({
      cylinder_type_id: '',
      quantity_received: 1,
      source_omc: '',
      challan_number: '',
      invoice_number: '',
      truck_number: '',
    });
    this.lastGrn.set(null);
    this.drawerError.set(null);
    this.showGrnModal.set(true);
  }

  protected onSubmitGrn(): void {
    const refId = this.locationRefId();
    if (!refId || this.grnForm.invalid) return;
    const val = this.grnForm.getRawValue();
    this.loading.set(true);
    this.inventoryService
      .recordGoodsReceipt(refId, {
        cylinder_type_id: val.cylinder_type_id,
        quantity_received: val.quantity_received,
        source_omc: val.source_omc || null,
        challan_number: val.challan_number.trim() || null,
        invoice_number: val.invoice_number.trim() || null,
        truck_number: val.truck_number.trim() || null,
      })
      .subscribe({
        next: (grn) => {
          // Stock is already recorded — refresh the grid now, then swap the
          // drawer to the (optional) weighment-sample step rather than
          // closing it, so the same "Receive Goods" action can flow
          // straight into logging the MDG-required 10% check.
          this.loading.set(false);
          this.notify.success(
            `${grn.grn_number ?? 'Goods receipt'} recorded — ${grn.quantity_received} cylinders.`,
          );
          this.reload();
          this.lastGrn.set(grn);
          const suggested = Math.max(1, Math.ceil(grn.quantity_received * 0.1));
          this.weighmentForm.reset({
            scale_id: this.activeScalesForWarehouse()[0]?.id ?? '',
            cylinders_checked: Math.min(suggested, grn.quantity_received),
            underweight_cylinder_count: 0,
          });
        },
        error: (err) => this.failInDrawer(err),
      });
  }

  /** Non-blocking — closes the drawer without recording a sample. */
  protected skipWeighmentSample(): void {
    this.showGrnModal.set(false);
    this.lastGrn.set(null);
  }

  protected onSubmitWeighmentSample(): void {
    const grn = this.lastGrn();
    if (!grn || this.weighmentForm.invalid) return;
    const val = this.weighmentForm.getRawValue();
    this.loading.set(true);
    this.weighmentService
      .recordGoodsReceiptWeighment(grn.id, {
        scale_id: val.scale_id,
        cylinder_type_id: grn.cylinder_type_id,
        total_cylinders_in_batch: grn.quantity_received,
        cylinders_checked: val.cylinders_checked,
        underweight_cylinder_count: val.underweight_cylinder_count,
      })
      .subscribe({
        next: () => {
          this.showGrnModal.set(false);
          this.lastGrn.set(null);
          this.notify.success('Weighment sample recorded.');
          this.loading.set(false);
        },
        error: (err) => this.failInDrawer(err),
      });
  }

  // ---------------------------------------------------------------------------
  // Load transfer
  // ---------------------------------------------------------------------------

  protected openTransferModal(): void {
    this.transferForm.reset({
      warehouse_id: this.warehouses()[0]?.id ?? '',
      vehicle_id: this.vehicles()[0]?.id ?? '',
      cylinder_type_id: '',
      status: 'filled',
      quantity: 1,
    });
    this.drawerError.set(null);
    this.showTransferModal.set(true);
  }

  protected onSubmitTransfer(): void {
    if (this.transferForm.invalid) return;
    const val = this.transferForm.getRawValue();
    this.loading.set(true);
    this.inventoryService
      .createLoadTransfer({
        warehouse_id: val.warehouse_id,
        vehicle_id: val.vehicle_id,
        lines: [
          {
            cylinder_type_id: val.cylinder_type_id,
            status: val.status as CylinderStatus,
            quantity: val.quantity,
          },
        ],
      })
      .subscribe({
        next: () => {
          this.showTransferModal.set(false);
          this.refreshAfterMutation('Load transfer recorded.');
        },
        error: (err) => this.failInDrawer(err),
      });
  }

  // ---------------------------------------------------------------------------
  // Delivery / collection (vehicle-only)
  // ---------------------------------------------------------------------------

  protected openDeliveryCollectionModal(): void {
    this.deliveryCollectionForm.reset({ mode: 'delivery', cylinder_type_id: '', quantity: 1 });
    this.drawerError.set(null);
    this.showDeliveryCollectionModal.set(true);
  }

  protected onSubmitDeliveryCollection(): void {
    const refId = this.locationRefId();
    if (!refId || this.deliveryCollectionForm.invalid) return;
    const val = this.deliveryCollectionForm.getRawValue();
    const body = { cylinder_type_id: val.cylinder_type_id, quantity: val.quantity };
    this.loading.set(true);
    const request$ =
      val.mode === 'delivery'
        ? this.inventoryService.recordDelivery(refId, body)
        : this.inventoryService.recordCollection(refId, body);
    request$.subscribe({
      next: () => {
        this.showDeliveryCollectionModal.set(false);
        this.refreshAfterMutation('Saved.');
      },
      error: (err) => this.failInDrawer(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Status change / adjust
  // ---------------------------------------------------------------------------

  protected openStatusChangeModal(): void {
    this.statusChangeForm.reset({
      cylinder_type_id: '',
      from_status: 'filled',
      to_status: this.firstTarget('status_change', 'filled'),
      quantity: 1,
    });
    this.drawerError.set(null);
    this.showStatusChangeModal.set(true);
  }

  protected onSubmitStatusChange(): void {
    const refId = this.locationRefId();
    if (!refId || this.statusChangeForm.invalid) return;
    const val = this.statusChangeForm.getRawValue();
    this.loading.set(true);
    this.inventoryService
      .changeCylinderStatus(this.locationType(), refId, {
        cylinder_type_id: val.cylinder_type_id,
        from_status: val.from_status as CylinderStatus,
        to_status: val.to_status as CylinderStatus,
        quantity: val.quantity,
      })
      .subscribe({
        next: () => {
          this.showStatusChangeModal.set(false);
          this.refreshAfterMutation('Status changed.');
        },
        error: (err) => this.failInDrawer(err),
      });
  }

  protected openAdjustModal(): void {
    this.adjustForm.reset({
      cylinder_type_id: '',
      from_status: 'filled',
      to_status: this.firstTarget('adjustment', 'filled'),
      quantity: 1,
      reason: '',
    });
    this.drawerError.set(null);
    this.showAdjustModal.set(true);
  }

  protected onSubmitAdjust(): void {
    const refId = this.locationRefId();
    if (!refId || this.adjustForm.invalid) return;
    const val = this.adjustForm.getRawValue();
    this.loading.set(true);
    this.inventoryService
      .adjustInventory(this.locationType(), refId, {
        cylinder_type_id: val.cylinder_type_id,
        from_status: val.from_status as CylinderStatus,
        to_status: val.to_status as CylinderStatus,
        quantity: val.quantity,
        reason: val.reason,
      })
      .subscribe({
        next: () => {
          this.showAdjustModal.set(false);
          this.refreshAfterMutation('Adjustment recorded.');
        },
        error: (err) => this.failInDrawer(err),
      });
  }

  // ---------------------------------------------------------------------------
  // Reconciliation
  // ---------------------------------------------------------------------------

  protected openReconcileModal(): void {
    const preselectedCt = this.selectedCylinderTypeId() ?? '';
    this.reconcileForm.reset({
      cylinder_type_id: preselectedCt,
      status: 'filled',
      actual_quantity: 0,
    });
    this.lastReconciliationRecordId.set(null);
    this.drawerError.set(null);
    this.showReconcileModal.set(true);
  }

  /** Records the count only — stock changes when someone else approves it. */
  protected onSubmitReconcile(): void {
    const refId = this.locationRefId();
    if (!refId || this.reconcileForm.invalid) return;
    const val = this.reconcileForm.getRawValue();
    this.loading.set(true);
    this.inventoryService
      .createReconciliationRecord(this.locationType(), refId, {
        cylinder_type_id: val.cylinder_type_id,
        status: val.status as CylinderStatus,
        actual_quantity: val.actual_quantity,
      })
      .subscribe({
        next: (record) => {
          this.lastReconciliationRecordId.set(record.id);
          this.loading.set(false);
          this.loadPendingCounts();
        },
        error: (err) => this.failInDrawer(err),
      });
  }

  protected loadPendingCounts(): void {
    const refId = this.locationRefId();
    if (!refId) return;
    this.inventoryService
      .listReconciliationRecords(this.locationType(), refId, 'pending')
      .subscribe({
        next: (records) => this.pendingCounts.set(records),
        error: () => this.pendingCounts.set([]),
      });
  }

  protected onApproveCount(record: ReconciliationRecordResponse): void {
    this.countsError.set(null);
    this.loading.set(true);
    this.inventoryService.approveReconciliationRecord(record.id).subscribe({
      next: () => this.refreshAfterMutation('Count approved — stock corrected.'),
      error: (err) => {
        this.countsError.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected openRejectCount(record: ReconciliationRecordResponse): void {
    this.rejectingCount.set(record);
    this.rejectForm.reset({ reason: '' });
    this.drawerError.set(null);
    this.showRejectModal.set(true);
  }

  protected onSubmitReject(): void {
    const record = this.rejectingCount();
    if (!record || this.rejectForm.invalid) return;
    this.loading.set(true);
    this.inventoryService
      .rejectReconciliationRecord(record.id, this.rejectForm.getRawValue().reason.trim())
      .subscribe({
        next: () => {
          this.showRejectModal.set(false);
          this.rejectingCount.set(null);
          this.refreshAfterMutation('Count rejected — stock unchanged.');
        },
        error: (err) => this.failInDrawer(err),
      });
  }

  // ---------------------------------------------------------------------------
  // Empties return to the OMC (DA-34)
  // ---------------------------------------------------------------------------

  protected openOmcReturnModal(): void {
    this.omcReturnForm.reset({
      destination_omc: '',
      cylinder_type_id: '',
      status: 'empty',
      quantity: 1,
      challan_number: '',
      truck_number: '',
    });
    this.drawerError.set(null);
    this.showOmcReturnModal.set(true);
  }

  protected onSubmitOmcReturn(): void {
    const refId = this.locationRefId();
    if (!refId || this.omcReturnForm.invalid) return;
    const val = this.omcReturnForm.getRawValue();
    const request: OmcReturnRequest = {
      destination_omc: val.destination_omc as OmcCode,
      cylinder_type_id: val.cylinder_type_id,
      status: val.status,
      quantity: val.quantity,
      challan_number: val.challan_number.trim() || null,
      truck_number: val.truck_number.trim() || null,
    };
    this.loading.set(true);
    this.inventoryService.returnStockToOmc(refId, request).subscribe({
      next: (note) => {
        this.showOmcReturnModal.set(false);
        this.refreshAfterMutation(`${note.return_number} recorded — ${note.quantity} cylinders.`);
      },
      error: (err) => this.failInDrawer(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Stock register (DA-34)
  // ---------------------------------------------------------------------------

  protected onRegisterRangeChange(which: 'from' | 'to', value: Date | null): void {
    if (!value) return;
    (which === 'from' ? this.registerFrom : this.registerTo).set(value);
    this.loadStockRegister();
  }

  protected loadStockRegister(): void {
    const refId = this.locationRefId();
    if (!refId) return;
    this.registerLoading.set(true);
    this.inventoryService
      .getStockRegister(
        this.locationType(),
        refId,
        toIsoDate(this.registerFrom()),
        toIsoDate(this.registerTo()),
      )
      .subscribe({
        next: (register) => {
          this.registerLines.set(register.lines);
          this.registerLoading.set(false);
        },
        error: (err) => {
          this.registerLines.set([]);
          this.registerLoading.set(false);
          this.errorMessage.set(errorMessageFor(err));
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Reorder policy (AI Operational Intelligence, Horizon 1 Stage 4)
  // ---------------------------------------------------------------------------

  private loadReorderPolicies(): void {
    this.inventoryService.listReorderPolicies().subscribe({
      next: (policies) => this.reorderPolicies.set(policies),
    });
  }

  private loadReorderSignals(): void {
    this.inventoryService.listReorderSignals().subscribe({
      next: (signals) => this.reorderSignals.set(signals),
    });
  }

  protected openReorderPolicyModal(): void {
    this.reorderPolicyForm.reset({
      warehouse_id: this.warehouses()[0]?.id ?? '',
      cylinder_type_id: '',
      reorder_point: 10,
      safety_stock: 0,
    });
    this.drawerError.set(null);
    this.showReorderPolicyModal.set(true);
  }

  protected onSubmitReorderPolicy(): void {
    if (this.reorderPolicyForm.invalid) return;
    const val = this.reorderPolicyForm.getRawValue();
    this.loading.set(true);
    this.inventoryService
      .setReorderPolicy({
        warehouse_id: val.warehouse_id,
        cylinder_type_id: val.cylinder_type_id,
        reorder_point: val.reorder_point,
        safety_stock: val.safety_stock,
      })
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.notify.success('Reorder policy saved.');
          this.loadReorderPolicies();
          this.loadReorderSignals();
        },
        error: (err) => this.failInDrawer(err),
      });
  }
}
