import { HeaderPortalDirective, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { HasPermissionDirective } from '@lpg/shared/ui';
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
import {
  FormsModule,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
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
  type AppError,
  type CylinderTypeResponse,
  type InventoryBalanceLine,
  type InventoryBalanceResponse,
  type InventoryLocationType,
  type InventoryTransactionResponse,
  type VehicleResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, PageHeaderComponent, StatusChipCell, toSentenceCase } from '@lpg/shared/ui';

const CYLINDER_STATUSES = [
  'filled',
  'empty',
  'damaged',
  'leakage',
  'quarantine',
  'repair',
  'scrap',
] as const;

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'INSUFFICIENT_STOCK':
      return 'Not enough stock available for that quantity.';
    case 'INVALID_STATUS_TRANSITION':
      return 'That status change is not permitted.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    default:
      return 'Something went wrong. Please try again.';
  }
}

@Component({
  selector: 'lpg-feature-inventory',
  standalone: true,
  imports: [PageHeaderComponent, HeaderTitlePortalDirective, HeaderPortalDirective, 
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    InputNumber,
    Textarea,
    Drawer,
    Message,
    Select,
    DataGridComponent,
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

  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly vehicles = signal<VehicleResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);

  protected readonly statusOptions = CYLINDER_STATUSES.map((s) => ({ label: toSentenceCase(s), value: s }));

  protected readonly locationType = signal<InventoryLocationType>('warehouse');
  protected readonly locationRefId = signal<string | null>(null);
  protected readonly balance = signal<InventoryBalanceResponse | null>(null);
  protected readonly transactions = signal<InventoryTransactionResponse[]>([]);
  protected readonly transactionsCursor = signal<string | null>(null);

  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);

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

  // Modal visibility
  protected readonly showGrnModal = signal(false);
  protected readonly showTransferModal = signal(false);
  protected readonly showDeliveryCollectionModal = signal(false);
  protected readonly showStatusChangeModal = signal(false);
  protected readonly showAdjustModal = signal(false);
  protected readonly showReconcileModal = signal(false);

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

  protected readonly balanceColumns: DataGridColumn<InventoryBalanceLine>[] = [
    {
      field: 'cylinder_type_id',
      header: 'Cylinder Type',
      sortable: true,
      valueFormatter: (value) =>
        this.cylinderTypeNameById().get(value as string) ?? (value as string),
    },
    { field: 'status', header: 'Status', sortable: true, cellRenderer: StatusChipCell },
    { field: 'quantity', header: 'Quantity', sortable: true, numeric: true },
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
    source_omc: [''],
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


  ngOnInit(): void {
    this.warehouseService.listWarehouses().subscribe({ next: (w) => this.warehouses.set(w) });
    this.deliveryService.listVehicles(0, 200).subscribe({
      next: (page) => this.vehicles.set(page.items),
    });
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (ct) => this.cylinderTypes.set(ct),
    });
  }

  protected onLocationTypeChange(value: InventoryLocationType): void {
    this.locationType.set(value);
    this.locationRefId.set(null);
    this.balance.set(null);
    this.transactions.set([]);
  }

  protected onLocationRefChange(value: string): void {
    this.locationRefId.set(value);
    this.loadBalance();
    this.loadTransactions();
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
    this.inventoryService.listTransactions(this.locationType(), refId, undefined, 50).subscribe({
      next: (page) => {
        this.transactions.set(page.items);
        this.transactionsCursor.set(page.next_cursor);
      },
      error: (err) => this.errorMessage.set(errorMessageFor(err)),
    });
  }

  protected loadMoreTransactions(): void {
    const refId = this.locationRefId();
    const cursor = this.transactionsCursor();
    if (!refId || !cursor) return;
    this.inventoryService.listTransactions(this.locationType(), refId, cursor, 50).subscribe({
      next: (page) => {
        this.transactions.set([...this.transactions(), ...page.items]);
        this.transactionsCursor.set(page.next_cursor);
      },
      error: (err) => this.errorMessage.set(errorMessageFor(err)),
    });
  }

  private refreshAfterMutation(): void {
    this.successMessage.set('Done.');
    this.loading.set(false);
    this.loadBalance();
    this.loadTransactions();
  }

  // ---------------------------------------------------------------------------
  // Goods Receipt (warehouse-only)
  // ---------------------------------------------------------------------------

  protected openGrnModal(): void {
    this.grnForm.reset({ cylinder_type_id: '', quantity_received: 1, source_omc: '' });
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
      })
      .subscribe({
        next: () => {
          this.showGrnModal.set(false);
          this.refreshAfterMutation();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
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
          { cylinder_type_id: val.cylinder_type_id, status: val.status, quantity: val.quantity },
        ],
      })
      .subscribe({
        next: () => {
          this.showTransferModal.set(false);
          this.refreshAfterMutation();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Delivery / collection (vehicle-only)
  // ---------------------------------------------------------------------------

  protected openDeliveryCollectionModal(): void {
    this.deliveryCollectionForm.reset({ mode: 'delivery', cylinder_type_id: '', quantity: 1 });
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
        this.refreshAfterMutation();
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  // ---------------------------------------------------------------------------
  // Status change / adjust
  // ---------------------------------------------------------------------------

  protected openStatusChangeModal(): void {
    this.statusChangeForm.reset({
      cylinder_type_id: '',
      from_status: 'filled',
      to_status: 'leakage',
      quantity: 1,
    });
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
        from_status: val.from_status,
        to_status: val.to_status,
        quantity: val.quantity,
      })
      .subscribe({
        next: () => {
          this.showStatusChangeModal.set(false);
          this.refreshAfterMutation();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected openAdjustModal(): void {
    this.adjustForm.reset({
      cylinder_type_id: '',
      from_status: 'filled',
      to_status: 'leakage',
      quantity: 1,
      reason: '',
    });
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
        from_status: val.from_status,
        to_status: val.to_status,
        quantity: val.quantity,
        reason: val.reason,
      })
      .subscribe({
        next: () => {
          this.showAdjustModal.set(false);
          this.refreshAfterMutation();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Reconciliation
  // ---------------------------------------------------------------------------

  protected openReconcileModal(): void {
    this.reconcileForm.reset({ cylinder_type_id: '', status: 'filled', actual_quantity: 0 });
    this.lastReconciliationRecordId.set(null);
    this.showReconcileModal.set(true);
  }

  protected onSubmitReconcile(): void {
    const refId = this.locationRefId();
    if (!refId || this.reconcileForm.invalid) return;
    const val = this.reconcileForm.getRawValue();
    this.loading.set(true);
    this.inventoryService
      .createReconciliationRecord(this.locationType(), refId, {
        cylinder_type_id: val.cylinder_type_id,
        status: val.status,
        actual_quantity: val.actual_quantity,
      })
      .subscribe({
        next: (record) => {
          this.lastReconciliationRecordId.set(record.id);
          this.loading.set(false);
          this.loadBalance();
          this.loadTransactions();
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  protected onApproveReconciliation(): void {
    const recordId = this.lastReconciliationRecordId();
    if (!recordId) return;
    this.loading.set(true);
    this.inventoryService.approveReconciliationRecord(recordId).subscribe({
      next: () => {
        this.showReconcileModal.set(false);
        this.refreshAfterMutation();
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }
}
