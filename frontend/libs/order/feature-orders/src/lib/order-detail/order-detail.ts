import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  FormFieldComponent,
  HasPermissionDirective,
  bookingSourceLabel,
  formatCurrencyInr,
  shortId,
} from '@lpg/shared/ui';
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
import { DatePipe, DecimalPipe } from '@angular/common';
import {
  FormsModule,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { debounceTime, filter, forkJoin } from 'rxjs';
import { ButtonDirective } from 'primeng/button';
import { DatePicker } from 'primeng/datepicker';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { InputGroup } from 'primeng/inputgroup';
import { InputGroupAddon } from 'primeng/inputgroupaddon';
import { InputNumber } from 'primeng/inputnumber';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Textarea } from 'primeng/textarea';
import { Tooltip } from 'primeng/tooltip';
import {
  AdminCylinderTypeService,
  AdminEmployeeService,
  AdminWarehouseService,
  AuthService,
  CustomerService,
  DeliveryService,
  InvoiceService,
  InventoryService,
  NotifyService,
  OrderService,
  WebSocketService,
  type AmendOrderRequest,
  type AppError,
  type CustomerAddressResponse,
  type CylinderTypeResponse,
  type DriverResponse,
  type EmployeeResponse,
  type InvoiceResponse,
  type InventoryBalanceLine,
  type RecordFailedDeliveryRequest,
  type OrderResponse,
  type OrderStatusHistoryEntryResponse,
  type PendingCancellationResponse,
  type ProofOfDeliveryResponse,
  type ProofOfDeliverySubmission,
  type RouteResponse,
  type VehicleResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';
import {
  DATE_INPUT_FORMAT,
  DATE_INPUT_PLACEHOLDER,
  FAILED_DELIVERY_REASON_LABELS,
  deliveryDayIso,
  errorMessageFor,
  statusLabel,
  statusSeverity,
} from '../order-status.util';

/** `order.status_changed` over the realtime socket (`realtime_handlers.py`). */
interface OrderStatusChangedMessage {
  type: 'order.status_changed';
  order_id: string;
  order_number: string | null;
  status: string;
  changed_by: string;
}

const FREE_CANCEL_STATUSES = new Set(['booked', 'confirmed', 'assigned', 'ready_for_dispatch']);
const APPROVAL_CANCEL_STATUSES = new Set(['out_for_delivery', 'failed_delivery']);

/** Trips that haven't come back yet; a driver or van on one is busy. */
const ACTIVE_TRIP_STATUSES = ['planned', 'loaded', 'in_progress'] as const;
/** Trips an order can still join from this page. */
const OPEN_TRIP_STATUSES = new Set(['planned', 'loaded']);
const NEW_TRIP = 'new';

/** The order's journey, one step per thing the counter staff can see. */
const PROGRESS_STEPS = ['Booked', 'Confirmed', 'On a trip', 'Out for delivery', 'Delivered'];
const PROGRESS_STEP_BY_STATUS: Record<string, number> = {
  booked: 0,
  confirmed: 1,
  assigned: 2,
  ready_for_dispatch: 2,
  out_for_delivery: 3,
  failed_delivery: 3,
  delivered: 4,
  closed: 4,
};

/** Send out errors in the order page's words; the rest use the shared text. */
function sendOutErrorMessage(error: unknown): string {
  switch ((error as Partial<AppError> | null)?.errorCode) {
    case 'INSUFFICIENT_STOCK':
      return "The godown doesn't have enough filled cylinders for this order. Receive stock or pick another godown.";
    case 'WEIGHMENT_CHECK_REQUIRED':
      return 'This agency weighs every cylinder before dispatch. Log the load-out weighment for this trip on the Dispatch page, then send it out again.';
    default:
      return errorMessageFor(error);
  }
}

const FAILED_DELIVERY_REASONS = [
  { label: 'Customer unavailable', value: 'customer_unavailable' },
  { label: 'Wrong address', value: 'wrong_address' },
  { label: 'Payment refused', value: 'payment_refused' },
  { label: 'Vehicle issue', value: 'vehicle_issue' },
  { label: 'Safety issue', value: 'safety_issue' },
] as const;

const RESOLUTION_ACTIONS = [
  { label: 'Reschedule', value: 'reschedule' },
  { label: 'Cancel', value: 'cancel' },
  { label: 'Return stock', value: 'return_stock' },
] as const;

/** Bookings the counter can still change before a trip is planned (DO-13). */
const AMENDABLE_STATUSES = new Set(['booked', 'confirmed']);

const PAYMENT_METHODS = [
  { label: 'Cash', value: 'cash' },
  { label: 'UPI', value: 'upi' },
  { label: 'Card', value: 'card' },
  { label: 'Online Gateway', value: 'online_gateway' },
  { label: 'Credit', value: 'credit' },
] as const;

@Component({
  selector: 'lpg-order-detail',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    HasPermissionDirective,
    DatePipe,
    DecimalPipe,
    DatePicker,
    RouterLink,
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    Drawer,
    DrawerA11yDirective,
    InputGroup,
    InputGroupAddon,
    InputNumber,
    InputText,
    Message,
    Select,
    Tag,
    Textarea,
    Tooltip,
    FormFieldComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './order-detail.html',
  styleUrl: './order-detail.css',
})
export class OrderDetail implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly orderService = inject(OrderService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly deliveryService = inject(DeliveryService);
  private readonly employeeService = inject(AdminEmployeeService);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly inventoryService = inject(InventoryService);
  private readonly customerService = inject(CustomerService);
  private readonly invoiceService = inject(InvoiceService);
  private readonly notify = inject(NotifyService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthService);
  private readonly wsService = inject(WebSocketService);

  constructor() {
    // Live-refresh when this order changes elsewhere (the driver departs or
    // delivers, another staff member confirms). The tenant-wide feed is the
    // same one the Order Queue uses; the socket has no unsubscribe, so one
    // shared intent beats one per order page visited.
    this.wsService.subscribeTo('orders');
    this.wsService
      .on<OrderStatusChangedMessage>('order.status_changed')
      .pipe(
        filter((message) => message.order_id === this.order()?.id),
        debounceTime(300),
        takeUntilDestroyed(),
      )
      .subscribe((message) => {
        this.load(message.order_id, { silent: true });
        // Your own actions already toast their result.
        if (message.changed_by !== this.auth.principal()?.userId) {
          const ref = message.order_number ?? shortId(message.order_id);
          this.notify.info(`${ref} is now ${statusLabel(message.status)}.`, 'Order updated');
        }
      });
    // Back after a dropped connection: catch up on anything missed.
    this.wsService.reconnected$.pipe(takeUntilDestroyed()).subscribe(() => {
      const id = this.order()?.id;
      if (id) this.load(id, { silent: true });
    });
  }

  protected readonly order = signal<OrderResponse | null>(null);
  protected readonly history = signal<OrderStatusHistoryEntryResponse[]>([]);
  /** The cancellation request waiting for Manager approval, if any (D-19). */
  protected readonly pendingCancellation = signal<PendingCancellationResponse | null>(null);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly drivers = signal<DriverResponse[]>([]);
  protected readonly vehicles = signal<VehicleResponse[]>([]);
  /** `DriverResponse` only carries `employee_id` (a UUID) — the Send out
   * drawer's driver select otherwise rendered every row with a blank label
   * (`optionLabel="employee_code"` doesn't exist on that type), making
   * drivers indistinguishable from each other. Resolved here the same way
   * customer/staff names are resolved elsewhere in this app: fetch once,
   * build a lookup, join client-side. */
  private readonly employeeById = signal<Map<string, EmployeeResponse>>(new Map());

  /** Delivery record of a delivered order (DO-26). */
  protected readonly proofOfDelivery = signal<ProofOfDeliveryResponse | null>(null);
  protected readonly invoices = signal<InvoiceResponse[]>([]);

  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly infoMessage = signal<string | null>(null);

  protected readonly showCancelDialog = signal(false);
  protected readonly showSendOutDrawer = signal(false);
  protected readonly showFailedDeliveryDrawer = signal(false);
  protected readonly showDeliverDrawer = signal(false);
  protected readonly showAmendDrawer = signal(false);
  protected readonly showRescheduleDrawer = signal(false);
  protected readonly showRejectCancelDrawer = signal(false);
  protected readonly amendAddresses = signal<CustomerAddressResponse[]>([]);

  protected readonly sendOutTrigger = viewChild<ElementRef<HTMLButtonElement>>('sendOutTriggerEl');
  protected readonly failedDeliveryTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('failedDeliveryTriggerEl');
  protected readonly deliverTrigger = viewChild<ElementRef<HTMLButtonElement>>('deliverTriggerEl');

  protected readonly cylinderTypeNameById = computed(() => {
    const map = new Map<string, string>();
    for (const ct of this.cylinderTypes()) map.set(ct.id, ct.name);
    return map;
  });

  private readonly driverNameById = computed(() => {
    const map = new Map<string, string>();
    for (const d of this.drivers()) {
      const employee = this.employeeById().get(d.employee_id);
      map.set(d.id, employee ? `${employee.first_name} ${employee.last_name}` : shortId(d.id));
    }
    return map;
  });

  private readonly vehicleNameById = computed(() => {
    const map = new Map<string, string>();
    for (const v of this.vehicles()) map.set(v.id, v.registration_number);
    return map;
  });

  /** Trips in this order's branch that haven't come back yet. */
  private readonly activeTrips = signal<RouteResponse[]>([]);

  private readonly busyOnTrip = computed(() => {
    const drivers = new Set<string>();
    const vehicles = new Set<string>();
    for (const trip of this.activeTrips()) {
      drivers.add(trip.driver_id);
      vehicles.add(trip.vehicle_id);
    }
    return { drivers, vehicles };
  });

  protected readonly driverOptions = computed(() =>
    this.drivers()
      .filter((d) => d.status === 'active' && d.branch_id === this.order()?.branch_id)
      .map((d) => {
        const busy = this.busyOnTrip().drivers.has(d.id);
        const name = this.driverNameById().get(d.id) ?? shortId(d.id);
        return { id: d.id, label: busy ? `${name} (on a trip)` : name, disabled: busy };
      }),
  );

  protected readonly vehicleOptions = computed(() =>
    this.vehicles()
      .filter((v) => v.status === 'active' && v.branch_id === this.order()?.branch_id)
      .map((v) => {
        const busy = this.busyOnTrip().vehicles.has(v.id);
        const name = `${v.registration_number} · holds ${v.capacity_units}`;
        return { id: v.id, label: busy ? `${name} (on a trip)` : name, disabled: busy };
      }),
  );

  /** The trip this order is already on, if it hasn't come back yet. */
  protected readonly orderTrip = computed(() => {
    const stopId = this.order()?.route_stop_id;
    if (!stopId) return null;
    return this.activeTrips().find((t) => (t.stops ?? []).some((s) => s.id === stopId)) ?? null;
  });

  protected tripLabel(trip: RouteResponse): string {
    const driver = this.driverNameById().get(trip.driver_id) ?? 'Driver';
    const van = this.vehicleNameById().get(trip.vehicle_id) ?? 'van';
    const state = trip.status === 'planned' ? 'not loaded' : 'ready to leave';
    const stops = (trip.stops ?? []).length;
    return `${driver} · ${van} · ${stops} ${stops === 1 ? 'order' : 'orders'}, ${state}`;
  }

  protected readonly progressSteps = PROGRESS_STEPS;

  /** Index of the current step, or null when the order left the normal path. */
  protected readonly progressIndex = computed(() => {
    const status = this.order()?.status;
    return status ? (PROGRESS_STEP_BY_STATUS[status] ?? null) : null;
  });

  protected readonly progressNote = computed(() => {
    const order = this.order();
    if (!order) return null;
    const trip = this.orderTrip();
    switch (order.status) {
      case 'confirmed':
        return 'Next: send it out on a trip.';
      case 'assigned':
        return trip
          ? `On ${this.tripLabel(trip)}. The van still needs loading.`
          : 'On a trip. The van still needs loading.';
      case 'ready_for_dispatch':
        return trip
          ? `Loaded on ${this.vehicleNameById().get(trip.vehicle_id) ?? 'the van'}, waiting for ${this.driverNameById().get(trip.driver_id) ?? 'the driver'} to leave.`
          : 'Loaded, waiting for the driver to leave.';
      case 'failed_delivery':
        return 'The delivery failed. Reschedule it to send it out again.';
      default:
        return null;
    }
  });

  // --- Send out ----------------------------------------------------------------

  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly sendTripId = signal<string>(NEW_TRIP);
  protected readonly sendDriverId = signal<string | null>(null);
  protected readonly sendVehicleId = signal<string | null>(null);
  protected readonly sendWarehouseId = signal<string | null>(null);
  protected readonly sendError = signal<string | null>(null);
  private readonly godownStock = signal<ReadonlyMap<string, number> | null>(null);
  private readonly vanStock = signal<ReadonlyMap<string, number>>(new Map());

  protected readonly sendTripOptions = computed(() => [
    { id: NEW_TRIP, label: 'New trip' },
    ...this.activeTrips()
      .filter((t) => OPEN_TRIP_STATUSES.has(t.status))
      .map((t) => ({ id: t.id, label: this.tripLabel(t) })),
  ]);

  protected readonly isNewTrip = computed(
    () => !this.orderTrip() && this.sendTripId() === NEW_TRIP,
  );

  /** The existing trip the order goes out on: the one it's on, or the one picked. */
  private readonly sendTrip = computed(
    () => this.orderTrip() ?? this.activeTrips().find((t) => t.id === this.sendTripId()) ?? null,
  );

  protected readonly sendVehicle = computed(() => {
    const vehicleId = this.sendTrip()?.vehicle_id ?? this.sendVehicleId();
    return this.vehicles().find((v) => v.id === vehicleId) ?? null;
  });

  protected readonly sendWarehouseOptions = computed(() => {
    const branchId = this.order()?.branch_id;
    const inBranch = this.warehouses().filter((w) => w.is_active && w.branch_id === branchId);
    return inBranch.length > 0 ? inBranch : this.warehouses().filter((w) => w.is_active);
  });

  /** This order's cylinders against the van and the godown: the server's arithmetic. */
  protected readonly sendLoadRows = computed(() => {
    const order = this.order();
    if (!order) return [];
    const godown = this.godownStock();
    const van = this.vanStock();
    // An order already on a trip keeps what was reserved for it; only the rest is loaded.
    const onTrip = order.status !== 'confirmed';
    return order.lines.map((line) => {
      const forOrder = onTrip ? line.quantity_pending : line.quantity_ordered;
      const onVan = van.get(line.cylinder_type_id) ?? 0;
      const toLoad = Math.max(0, forOrder - onVan);
      const inGodown = godown ? (godown.get(line.cylinder_type_id) ?? 0) : null;
      return {
        id: line.id,
        name:
          this.cylinderTypeNameById().get(line.cylinder_type_id) ?? shortId(line.cylinder_type_id),
        forOrder,
        onVan,
        toLoad,
        inGodown,
        short: inGodown !== null && toLoad > inGodown,
      };
    });
  });

  protected readonly sendShort = computed(() => this.sendLoadRows().some((row) => row.short));

  /** Other orders on the same not-yet-loaded trip go out with this one. */
  protected readonly sendCompanionCount = computed(() => {
    const trip = this.sendTrip();
    if (!trip || trip.status !== 'planned') return 0;
    const orderId = this.order()?.id;
    return (trip.stops ?? []).filter((s) => s.status === 'pending' && s.order_id !== orderId)
      .length;
  });

  protected readonly canSubmitSendOut = computed(
    () =>
      !this.loading() &&
      !!this.sendWarehouseId() &&
      !this.sendShort() &&
      (!this.isNewTrip() || (!!this.sendDriverId() && !!this.sendVehicleId())),
  );

  protected readonly canCancelFree = computed(() => {
    const status = this.order()?.status;
    return !!status && FREE_CANCEL_STATUSES.has(status);
  });

  /** A dispatched order with no request yet: cancelling asks a Manager to approve. */
  protected readonly requiresCancelApproval = computed(() => {
    const status = this.order()?.status;
    return !!status && APPROVAL_CANCEL_STATUSES.has(status) && !this.pendingCancellation();
  });

  /** Only when a cancellation request is actually waiting; the button also needs
   * the orders:cancel_approve permission. */
  protected readonly canApproveCancellation = computed(() => {
    const status = this.order()?.status;
    return !!status && APPROVAL_CANCEL_STATUSES.has(status) && !!this.pendingCancellation();
  });

  protected readonly canConfirm = computed(() => this.order()?.status === 'booked');
  /** A confirmed order, or one on a trip whose van isn't loaded yet. */
  protected readonly canSendOut = computed(() => {
    const status = this.order()?.status;
    return status === 'confirmed' || status === 'assigned';
  });
  protected readonly canDepart = computed(() => this.order()?.status === 'ready_for_dispatch');
  protected readonly canDeliverOrFail = computed(() => this.order()?.status === 'out_for_delivery');
  protected readonly canReschedule = computed(() => this.order()?.status === 'failed_delivery');
  protected readonly canClose = computed(() => this.order()?.status === 'delivered');
  protected readonly canAmend = computed(() => {
    const status = this.order()?.status;
    return !!status && AMENDABLE_STATUSES.has(status);
  });

  /** Why the last delivery failed, from the timeline (DO-14). */
  protected readonly failedReason = computed(() => {
    if (this.order()?.status !== 'failed_delivery') return null;
    const entry = [...this.history()].reverse().find((e) => e.to_status === 'failed_delivery');
    if (!entry?.reason) return null;
    return FAILED_DELIVERY_REASON_LABELS[entry.reason] ?? entry.reason;
  });

  protected readonly today = startOfToday();
  protected readonly dateInputFormat = DATE_INPUT_FORMAT;
  protected readonly dateInputPlaceholder = DATE_INPUT_PLACEHOLDER;

  protected readonly amendForm = this.fb.group({
    requested_date: [startOfToday(), [Validators.required]],
    address_id: ['', [Validators.required]],
    payment_method_preference: ['' as string],
    lines: this.fb.array<ReturnType<typeof this.buildAmendLineGroup>>([]),
  });

  protected readonly rescheduleForm = this.fb.group({
    requested_date: [startOfToday(), [Validators.required]],
  });

  protected readonly rejectCancelForm = this.fb.group({
    reason: ['', [Validators.required, Validators.maxLength(1000)]],
  });

  protected readonly cancelForm = this.fb.group({
    reason: ['', [Validators.required, Validators.minLength(3)]],
  });

  protected readonly failedDeliveryForm = this.fb.group({
    reason_code: ['customer_unavailable', [Validators.required]],
    resolution_action: ['reschedule', [Validators.required]],
  });

  protected readonly deliverForm = this.fb.group({
    otp_code: ['', [Validators.required]],
    // Delivery Authentication Code (Phase 20 subsystem 4) — the OMC's own
    // separate 6-digit code, distinct from the OTP above. Optional
    // (coverage is ~90%, not 100%) — the pattern validator short-circuits
    // on an empty value, so this never blocks submission on its own.
    dac_code: ['', [Validators.pattern(/^\d{6}$/)]],
    payment_method: ['cash', [Validators.required]],
    amount_collected: [0, [Validators.required, Validators.min(0)]],
    gps_lat: [0, [Validators.required]],
    gps_lng: [0, [Validators.required]],
    lines: this.fb.array<ReturnType<typeof this.buildDeliverLineGroup>>([]),
  });

  protected readonly fieldMessages = {
    requested_date: { required: 'Pick a delivery date.' },
    address_id: { required: 'Pick a delivery address.' },
    quantity: { required: 'Enter a quantity.', min: 'At least 0.' },
    reject_reason: {
      required: 'Tell the requester why.',
      maxlength: 'Keep it under 1000 characters.',
    },
    reason: {
      required: 'A reason is required.',
      minlength: 'Give a little more detail.',
    },
    reason_code: { required: 'Select a reason.' },
    resolution_action: { required: 'Select a resolution.' },
    otp_code: { required: 'The delivery OTP is required.' },
    dac_code: { pattern: 'The DAC is a 6-digit code — leave it blank if the customer has none.' },
    payment_method: { required: 'Select a payment method.' },
    amount_collected: { required: 'Enter the amount collected.', min: 'Cannot be negative.' },
  };

  protected readonly signatureBlobRef = signal<string | null>(null);
  protected readonly photoBlobRef = signal<string | null>(null);
  protected readonly uploadingSignature = signal(false);
  protected readonly uploadingPhoto = signal(false);
  protected readonly gpsCaptured = signal(false);

  protected readonly signatureCanvas = viewChild<ElementRef<HTMLCanvasElement>>('signatureCanvas');
  private drawing = false;
  private hasSignatureStrokes = false;

  // The signature and photo are optional — the OTP and the GPS stamp are the required proof.
  protected readonly deliverReady = computed(() => this.gpsCaptured());

  protected readonly statusLabel = statusLabel;
  protected readonly formatCurrencyInr = formatCurrencyInr;
  protected readonly bookingSourceLabel = bookingSourceLabel;
  protected readonly statusSeverity = statusSeverity;
  protected readonly failedDeliveryReasons = [...FAILED_DELIVERY_REASONS];
  protected readonly resolutionActions = [...RESOLUTION_ACTIONS];
  protected readonly paymentMethods = [...PAYMENT_METHODS];

  ngOnInit(): void {
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (ct) => this.cylinderTypes.set(ct),
    });
    this.route.paramMap.subscribe((params) => {
      const orderId = params.get('id');
      if (orderId) this.load(orderId);
    });
  }

  private load(orderId: string, { silent = false } = {}): void {
    // A live refresh keeps the page on screen instead of flashing the spinner.
    if (!silent) this.loading.set(true);
    this.errorMessage.set(null);
    this.orderService.getOrder(orderId).subscribe({
      next: (order) => {
        const branchChanged = order.branch_id !== this.order()?.branch_id;
        this.order.set(order);
        this.loading.set(false);
        if (this.drivers().length === 0) this.loadFleet();
        if (order.route_stop_id || branchChanged) this.loadActiveTrips(order.branch_id);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
    this.orderService.listOrderStatusHistory(orderId).subscribe({
      next: (entries) => this.history.set(entries),
      error: () => this.history.set([]),
    });
    this.orderService.getPendingCancellation(orderId).subscribe({
      next: (pending) => this.pendingCancellation.set(pending),
      error: () => this.pendingCancellation.set(null),
    });
    this.orderService.getProofOfDelivery(orderId).subscribe({
      next: (pod) => this.proofOfDelivery.set(pod),
      error: () => this.proofOfDelivery.set(null),
    });
    if (this.auth.principal()?.permissions.has('invoices:read')) {
      this.invoiceService.list(1, 10, undefined, orderId).subscribe({
        next: (page) => this.invoices.set(page.items),
        error: () => this.invoices.set([]),
      });
    }
  }

  protected refresh(): void {
    const orderId = this.order()?.id;
    if (orderId) this.load(orderId);
  }

  private applyUpdate(order: OrderResponse, message: string): void {
    this.order.set(order);
    this.infoMessage.set(message);
    this.errorMessage.set(null);
    this.loading.set(false);
    this.notify.success(message);
    this.refresh();
  }

  private applyError(err: unknown): void {
    this.errorMessage.set(errorMessageFor(err));
    this.loading.set(false);
  }

  /** Every driver and van, for names on trips; Send out offers the order's branch only.
   * A trip can use a van registered to another branch, so names can't be branch-filtered. */
  private loadFleet(): void {
    this.deliveryService.listDrivers(0, 200).subscribe({
      next: (page) => this.drivers.set(page.items),
    });
    this.deliveryService.listVehicles(0, 200).subscribe({
      next: (page) => this.vehicles.set(page.items),
    });
    this.employeeService.listEmployees({ limit: 200, role: 'driver' }).subscribe({
      next: (page) => {
        const map = new Map<string, EmployeeResponse>();
        for (const employee of page.items) map.set(employee.id, employee);
        this.employeeById.set(map);
      },
    });
  }

  private loadActiveTrips(branchId: string): void {
    // `/routes` needs `routes:read`; roles without it (e.g. an accountant)
    // would only get a 403 — skip the call (DO-31).
    if (!this.auth.principal()?.permissions.has('routes:read')) {
      this.activeTrips.set([]);
      return;
    }
    forkJoin(
      ACTIVE_TRIP_STATUSES.map((status) =>
        this.deliveryService.listRoutes(1, 100, status, branchId),
      ),
    ).subscribe({
      next: (pages) => this.activeTrips.set(pages.flatMap((page) => page.items)),
      error: () => this.activeTrips.set([]),
    });
  }

  // ---------------------------------------------------------------------------
  // Confirm / Depart / Reschedule / Close — direct status advances
  // ---------------------------------------------------------------------------

  protected onConfirm(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.confirmOrder(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Order confirmed.'),
      error: (err) => this.applyError(err),
    });
  }

  protected onDepart(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.departOrder(order.id).subscribe({
      next: (updated) =>
        this.applyUpdate(updated, 'Driver departed — delivery OTP sent to the customer.'),
      error: (err) => this.applyError(err),
    });
  }

  protected openRescheduleDrawer(): void {
    this.rescheduleForm.reset({ requested_date: startOfToday() });
    this.showRescheduleDrawer.set(true);
  }

  /** Back to Confirmed for the picked day; Send out puts it on a trip again. */
  protected onReschedule(): void {
    const order = this.order();
    if (!order || this.rescheduleForm.invalid) {
      this.rescheduleForm.markAllAsTouched();
      return;
    }
    const { requested_date } = this.rescheduleForm.getRawValue();
    this.loading.set(true);
    this.orderService.rescheduleOrder(order.id, deliveryDayIso(requested_date)).subscribe({
      next: (updated) => {
        this.showRescheduleDrawer.set(false);
        this.applyUpdate(updated, 'Delivery rescheduled. Send it out again when ready.');
      },
      error: (err) => this.applyError(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Edit booking (DO-13)
  // ---------------------------------------------------------------------------

  private buildAmendLineGroup(cylinderTypeId: string, quantity: number) {
    return this.fb.group({
      cylinder_type_id: [cylinderTypeId],
      quantity: [quantity, [Validators.required, Validators.min(0)]],
    });
  }

  protected get amendLines() {
    return this.amendForm.controls.lines;
  }

  protected openAmendDrawer(): void {
    const order = this.order();
    if (!order) return;
    const requested = new Date(order.requested_date);
    this.amendForm.reset({
      requested_date: requested < this.today ? startOfToday() : requested,
      address_id: '',
      payment_method_preference: order.payment_method_preference ?? '',
    });
    this.amendLines.clear();
    for (const line of order.lines) {
      this.amendLines.push(this.buildAmendLineGroup(line.cylinder_type_id, line.quantity_ordered));
    }
    this.amendAddresses.set([]);
    if (order.customer) {
      this.customerService.get(order.customer.id).subscribe({
        next: (customer) => {
          this.amendAddresses.set(customer.addresses);
          const current = customer.addresses.find(
            (a) => a.line_1 === order.delivery_address.address_line,
          );
          const fallback = customer.addresses.find((a) => a.is_primary) ?? customer.addresses[0];
          this.amendForm.controls.address_id.setValue((current ?? fallback)?.id ?? '');
        },
      });
    }
    this.showAmendDrawer.set(true);
  }

  protected amendAddressLabel(address: CustomerAddressResponse): string {
    return [address.line_1, address.area, address.city, address.pincode]
      .filter((part) => !!part)
      .join(', ');
  }

  protected onSubmitAmend(): void {
    const order = this.order();
    if (!order || this.amendForm.invalid) {
      this.amendForm.markAllAsTouched();
      return;
    }
    const value = this.amendForm.getRawValue();
    const lines = value.lines.filter((line) => line.quantity > 0);
    if (lines.length === 0) {
      this.errorMessage.set('Keep at least one cylinder, or cancel the order instead.');
      return;
    }
    this.loading.set(true);
    this.orderService
      .amendOrder(order.id, {
        requested_date: deliveryDayIso(value.requested_date),
        address_id: value.address_id,
        payment_method_preference: (value.payment_method_preference || null) as AmendPaymentMethod,
        lines,
      })
      .subscribe({
        next: (updated) => {
          this.showAmendDrawer.set(false);
          this.applyUpdate(updated, 'Booking updated.');
        },
        error: (err) => this.applyError(err),
      });
  }

  protected onClose(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.closeOrder(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Order closed.'),
      error: (err) => this.applyError(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Send out — pick a trip and a godown, load the van and dispatch in one step
  // ---------------------------------------------------------------------------

  protected openSendOutDrawer(): void {
    const order = this.order();
    if (!order) return;
    this.sendError.set(null);
    this.sendTripId.set(NEW_TRIP);
    this.sendDriverId.set(null);
    this.onSendVehicleChange(this.orderTrip()?.vehicle_id ?? null);
    if (this.warehouses().length === 0) {
      this.warehouseService.listWarehouses().subscribe({
        next: (warehouses) => {
          this.warehouses.set(warehouses);
          this.onSendWarehouseChange(this.sendWarehouseOptions()[0]?.id ?? null);
        },
        error: () => this.sendError.set('Failed to load godowns.'),
      });
    } else {
      this.onSendWarehouseChange(this.sendWarehouseOptions()[0]?.id ?? null);
    }
    this.loadActiveTrips(order.branch_id);
    this.showSendOutDrawer.set(true);
  }

  protected onSendTripChange(tripId: string): void {
    this.sendTripId.set(tripId);
    const trip = this.activeTrips().find((t) => t.id === tripId);
    this.onSendVehicleChange(trip?.vehicle_id ?? this.sendVehicleId());
  }

  protected onSendVehicleChange(vehicleId: string | null): void {
    if (this.isNewTrip() || !vehicleId) this.sendVehicleId.set(vehicleId);
    this.vanStock.set(new Map());
    if (!vehicleId) return;
    this.inventoryService.getBalance('vehicle', vehicleId).subscribe({
      next: (balance) => this.vanStock.set(filledStock(balance.balances)),
    });
  }

  protected onSendWarehouseChange(warehouseId: string | null): void {
    this.sendWarehouseId.set(warehouseId);
    this.godownStock.set(null);
    if (!warehouseId) return;
    this.inventoryService.getBalance('warehouse', warehouseId).subscribe({
      next: (balance) => this.godownStock.set(filledStock(balance.balances)),
      // Stock is a guide here; the server still refuses a short load.
      error: () => this.godownStock.set(null),
    });
  }

  protected onSubmitSendOut(): void {
    const order = this.order();
    if (!order || !this.canSubmitSendOut()) return;
    this.loading.set(true);
    this.sendError.set(null);
    const trip = this.sendTrip();
    if (trip) {
      this.loadAndDispatch(order, trip);
      return;
    }
    const requested = new Date(order.requested_date);
    const now = new Date();
    this.deliveryService
      .planRoute({
        branch_id: order.branch_id,
        driver_id: this.sendDriverId() as string,
        vehicle_id: this.sendVehicleId() as string,
        route_date: (requested > now ? requested : now).toISOString(),
      })
      .subscribe({
        next: (route) => {
          // A retry after a failed load joins this trip instead of making another.
          this.activeTrips.set([...this.activeTrips(), route]);
          this.sendTripId.set(route.id);
          this.loadAndDispatch(order, route);
        },
        error: (err) => this.failSendOut(err),
      });
  }

  private loadAndDispatch(order: OrderResponse, trip: RouteResponse): void {
    this.deliveryService
      .loadAndDispatchRoute(trip.id, {
        warehouse_id: this.sendWarehouseId() as string,
        order_ids: order.status === 'confirmed' ? [order.id] : [],
        extra_lines: [],
      })
      .subscribe({
        next: () => {
          this.showSendOutDrawer.set(false);
          const driver = this.driverNameById().get(trip.driver_id) ?? 'the driver';
          this.loading.set(false);
          this.infoMessage.set(null);
          this.notify.success(`Loaded and handed to ${driver}.`);
          this.refresh();
          this.loadActiveTrips(order.branch_id);
        },
        error: (err) => this.failSendOut(err),
      });
  }

  private failSendOut(err: unknown): void {
    this.sendError.set(sendOutErrorMessage(err));
    this.loading.set(false);
  }

  // ---------------------------------------------------------------------------
  // Failed delivery
  // ---------------------------------------------------------------------------

  protected openFailedDeliveryDrawer(): void {
    this.failedDeliveryForm.reset({
      reason_code: 'customer_unavailable',
      resolution_action: 'reschedule',
    });
    this.showFailedDeliveryDrawer.set(true);
  }

  protected onSubmitFailedDelivery(): void {
    const order = this.order();
    if (!order || this.failedDeliveryForm.invalid) return;
    const { reason_code, resolution_action } = this.failedDeliveryForm.getRawValue();
    this.loading.set(true);
    const request: RecordFailedDeliveryRequest = {
      reason_code: reason_code as RecordFailedDeliveryRequest['reason_code'],
      resolution_action: resolution_action as RecordFailedDeliveryRequest['resolution_action'],
    };
    this.orderService.recordFailedDelivery(order.id, request).subscribe({
      next: (updated) => {
        this.showFailedDeliveryDrawer.set(false);
        this.applyUpdate(updated, 'Failed delivery recorded.');
      },
      error: (err) => this.applyError(err),
    });
  }

  // ---------------------------------------------------------------------------
  // Deliver (OTP + Proof of Delivery: signature pad, photo, GPS)
  // ---------------------------------------------------------------------------

  private buildDeliverLineGroup(cylinderTypeId: string, maxQuantity: number) {
    return this.fb.group({
      cylinder_type_id: [cylinderTypeId],
      quantity_delivered: [maxQuantity, [Validators.required, Validators.min(0)]],
      quantity_collected_empty: [0, [Validators.required, Validators.min(0)]],
    });
  }

  protected get deliverLines() {
    return this.deliverForm.controls.lines;
  }

  protected openDeliverDrawer(): void {
    const order = this.order();
    if (!order) return;
    this.deliverForm.reset({
      otp_code: '',
      dac_code: '',
      payment_method: 'cash',
      amount_collected: 0,
      gps_lat: 0,
      gps_lng: 0,
    });
    this.deliverForm.controls.lines.clear();
    for (const line of order.lines) {
      this.deliverForm.controls.lines.push(
        this.buildDeliverLineGroup(
          line.cylinder_type_id,
          line.quantity_ordered - line.quantity_pending,
        ),
      );
    }
    this.signatureBlobRef.set(null);
    this.photoBlobRef.set(null);
    this.gpsCaptured.set(false);
    this.hasSignatureStrokes = false;
    this.showDeliverDrawer.set(true);
    // The canvas isn't in the DOM until the drawer's content projects it.
    queueMicrotask(() => this.clearSignature());
  }

  protected captureLocation(): void {
    if (!navigator.geolocation) {
      this.errorMessage.set('Geolocation is not available on this device.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.deliverForm.patchValue({
          gps_lat: position.coords.latitude,
          gps_lng: position.coords.longitude,
        });
        this.gpsCaptured.set(true);
      },
      () => this.errorMessage.set('Could not read the device location.'),
    );
  }

  // --- Signature pad -------------------------------------------------------

  protected onSignatureDown(event: PointerEvent): void {
    const canvas = this.signatureCanvas()?.nativeElement;
    if (!canvas) return;
    this.drawing = true;
    const rect = canvas.getBoundingClientRect();
    const ctx = canvas.getContext('2d');
    ctx?.beginPath();
    ctx?.moveTo(event.clientX - rect.left, event.clientY - rect.top);
  }

  protected onSignatureMove(event: PointerEvent): void {
    if (!this.drawing) return;
    const canvas = this.signatureCanvas()?.nativeElement;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#000';
    ctx.lineTo(event.clientX - rect.left, event.clientY - rect.top);
    ctx.stroke();
    this.hasSignatureStrokes = true;
  }

  protected onSignatureUp(): void {
    this.drawing = false;
  }

  protected clearSignature(): void {
    const canvas = this.signatureCanvas()?.nativeElement;
    if (!canvas) return;
    canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
    this.hasSignatureStrokes = false;
    this.signatureBlobRef.set(null);
  }

  protected uploadSignature(): void {
    const order = this.order();
    const canvas = this.signatureCanvas()?.nativeElement;
    if (!order || !canvas || !this.hasSignatureStrokes) return;
    this.uploadingSignature.set(true);
    canvas.toBlob((blob) => {
      if (!blob) {
        this.uploadingSignature.set(false);
        return;
      }
      const file = new File([blob], 'signature.png', { type: 'image/png' });
      this.orderService.uploadPodAttachment(order.id, file).subscribe({
        next: (res) => {
          this.signatureBlobRef.set(res.blob_ref);
          this.uploadingSignature.set(false);
        },
        error: (err) => {
          this.applyError(err);
          this.uploadingSignature.set(false);
        },
      });
    }, 'image/png');
  }

  // --- Photo -----------------------------------------------------------------

  protected onPhotoSelected(event: Event): void {
    const order = this.order();
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!order || !file) return;
    this.uploadingPhoto.set(true);
    this.orderService.uploadPodAttachment(order.id, file).subscribe({
      next: (res) => {
        this.photoBlobRef.set(res.blob_ref);
        this.uploadingPhoto.set(false);
      },
      error: (err) => {
        this.applyError(err);
        this.uploadingPhoto.set(false);
      },
    });
  }

  protected onSubmitDeliver(): void {
    const order = this.order();
    const signatureBlobRef = this.signatureBlobRef();
    const photoBlobRef = this.photoBlobRef();
    if (!order || this.deliverForm.invalid) return;
    const val = this.deliverForm.getRawValue();
    this.loading.set(true);
    const proofOfDelivery: ProofOfDeliverySubmission = {
      ...(signatureBlobRef ? { signature_blob_ref: signatureBlobRef } : {}),
      ...(photoBlobRef ? { photo_blob_ref: photoBlobRef } : {}),
      gps_lat: val.gps_lat,
      gps_lng: val.gps_lng,
      payment_method: val.payment_method as ProofOfDeliverySubmission['payment_method'],
      amount_collected: val.amount_collected,
      dac_code: val.dac_code || null,
    };
    this.orderService
      .deliverOrder(order.id, {
        otp_code: val.otp_code,
        lines: val.lines.map((line) => ({
          cylinder_type_id: line.cylinder_type_id,
          quantity_delivered: line.quantity_delivered,
          quantity_collected_empty: line.quantity_collected_empty,
        })),
        proof_of_delivery: proofOfDelivery,
      })
      .subscribe({
        next: (result) => {
          this.showDeliverDrawer.set(false);
          this.applyUpdate(result.order, 'Delivery recorded.');
        },
        error: (err) => this.applyError(err),
      });
  }

  // ---------------------------------------------------------------------------
  // Cancel / Approve
  // ---------------------------------------------------------------------------

  protected openCancelDialog(): void {
    this.cancelForm.reset({ reason: '' });
    this.showCancelDialog.set(true);
  }

  protected onSubmitCancel(): void {
    const order = this.order();
    if (!order || this.cancelForm.invalid) return;
    const { reason } = this.cancelForm.getRawValue();
    this.loading.set(true);
    this.orderService.cancelOrder(order.id, { reason }).subscribe({
      next: (result) => {
        this.showCancelDialog.set(false);
        const message = result.pending_approval
          ? 'Cancellation requested — awaiting Manager approval.'
          : 'Order cancelled.';
        // A pending request shows its own banner once the page reloads.
        this.infoMessage.set(result.pending_approval ? null : message);
        this.notify.success(message);
        this.order.set(result.order);
        this.loading.set(false);
        this.refresh();
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected onApproveCancellation(): void {
    const order = this.order();
    if (!order) return;
    this.loading.set(true);
    this.orderService.approveOrderCancellation(order.id).subscribe({
      next: (updated) => this.applyUpdate(updated, 'Cancellation approved.'),
      error: (err) => this.applyError(err),
    });
  }

  protected openRejectCancelDrawer(): void {
    this.rejectCancelForm.reset({ reason: '' });
    this.showRejectCancelDrawer.set(true);
  }

  /** The order carries on; the requester sees why (DO-14). */
  protected onRejectCancellation(): void {
    const order = this.order();
    if (!order || this.rejectCancelForm.invalid) {
      this.rejectCancelForm.markAllAsTouched();
      return;
    }
    const reason = this.rejectCancelForm.getRawValue().reason.trim();
    this.loading.set(true);
    this.orderService.rejectOrderCancellation(order.id, reason).subscribe({
      next: () => {
        this.showRejectCancelDrawer.set(false);
        this.loading.set(false);
        this.notify.success('Cancellation request rejected. The order carries on.');
        this.refresh();
      },
      error: (err) => this.applyError(err),
    });
  }

  protected backToQueue(): void {
    void this.router.navigate(['/orders']);
  }
}

type AmendPaymentMethod = AmendOrderRequest['payment_method_preference'];

function startOfToday(): Date {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today;
}

function filledStock(balances: InventoryBalanceLine[]): Map<string, number> {
  const stock = new Map<string, number>();
  for (const line of balances) {
    if (line.status === 'filled') {
      stock.set(line.cylinder_type_id, (stock.get(line.cylinder_type_id) ?? 0) + line.quantity);
    }
  }
  return stock;
}
