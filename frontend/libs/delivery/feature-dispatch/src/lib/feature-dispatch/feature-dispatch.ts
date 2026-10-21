import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { FormFieldComponent, HasPermissionDirective, shortId } from '@lpg/shared/ui';
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
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { debounceTime } from 'rxjs';
import { ButtonDirective } from 'primeng/button';
import { Checkbox } from 'primeng/checkbox';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { InputNumber } from 'primeng/inputnumber';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { DatePicker } from 'primeng/datepicker';
import { Tooltip } from 'primeng/tooltip';
import {
  AuthTokenStore,
  AdminBranchService,
  AdminCylinderTypeService,
  AdminEmployeeService,
  AdminWarehouseService,
  AuthService,
  DeliveryService,
  InventoryService,
  NotifyService,
  OrderService,
  WebSocketService,
  WeighmentService,
  errorMessageFor as sharedErrorMessageFor,
  type AppError,
  type BranchResponse,
  type CashHandoverResponse,
  type CylinderTypeResponse,
  type DriverResponse,
  type EmployeeResponse,
  type InventoryBalanceLine,
  type OrderResponse,
  type RouteResponse,
  type ScaleResponse,
  type VehicleResponse,
  type WarehouseResponse,
  type WeighmentRecordResponse,
} from '@lpg/shared/data-access';

const ROUTE_STATUS_COLUMNS = [
  'planned',
  'loaded',
  'in_progress',
  'completed',
  'reconciled',
  'cancelled',
] as const;

// Named for what staff do next with the trip, not the internal state.
const ROUTE_STATUS_LABELS: Record<string, string> = {
  planned: 'Not loaded',
  loaded: 'Ready to leave',
  in_progress: 'On the road',
  completed: 'Back, to settle',
  reconciled: 'Settled',
  cancelled: 'Cancelled',
};

const STOP_STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  en_route: 'On the way',
  delivered: 'Delivered',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

const ROUTE_STATUS_SEVERITY: Record<string, 'success' | 'info' | 'warn' | 'danger' | 'secondary'> =
  {
    planned: 'secondary',
    loaded: 'info',
    in_progress: 'warn',
    completed: 'success',
    reconciled: 'success',
    cancelled: 'danger',
    pending: 'secondary',
    en_route: 'warn',
    delivered: 'success',
    failed: 'danger',
  };

/** Routes can only be cancelled while still `planned` or `loaded` (see
 * `RouteStatus` transition table in `domain/delivery/route.py`) — once a
 * route is `in_progress` it has to run to completion. */
const CANCELLABLE_ROUTE_STATUSES = new Set(['planned', 'loaded']);

/** A trip that hasn't come back yet. */
const ACTIVE_ROUTE_STATUSES = new Set(['planned', 'loaded', 'in_progress']);

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'ROUTE_RECONCILIATION_PENDING':
      return "This trip's vehicle needs an approved reconciliation before it can be settled. Approve one from Inventory first.";
    case 'INVALID_STATE_TRANSITION':
      return 'That action is not valid for the trip in its current state.';
    case 'INSUFFICIENT_STOCK':
      return "The godown doesn't have enough filled cylinders for this trip. Receive stock or remove some orders.";
    case 'WEIGHMENT_CHECK_REQUIRED':
      return 'This agency weighs every cylinder before dispatch. Open the trip, use "Log Load-Out Weighment" for each cylinder type, then load again.';
    default:
      return sharedErrorMessageFor(error);
  }
}

function toDateOnlyString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

@Component({
  selector: 'lpg-feature-dispatch',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    DatePipe,
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    Checkbox,
    Drawer,
    DrawerA11yDirective,
    InputNumber,
    Message,
    Select,
    Tag,
    DatePicker,
    Tooltip,
    FormFieldComponent,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-dispatch.html',
  styleUrl: './feature-dispatch.css',
})
export class FeatureDispatch implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly deliveryService = inject(DeliveryService);
  private readonly orderService = inject(OrderService);
  private readonly branchService = inject(AdminBranchService);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly employeeService = inject(AdminEmployeeService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly inventoryService = inject(InventoryService);
  private readonly weighmentService = inject(WeighmentService);
  private readonly authTokenStore = inject(AuthTokenStore);
  private readonly notify = inject(NotifyService);
  private readonly router = inject(Router);
  private readonly authService = inject(AuthService);
  private readonly wsService = inject(WebSocketService);

  constructor() {
    // DO-24: keep the board live. Order status changes (a new confirmed
    // order waiting for a trip, a cancellation) arrive on the orders feed;
    // trip changes (load, depart, deliver, fail) on the dispatch feed. A
    // reconnect refetches whatever was missed while the socket was down.
    this.wsService.subscribeTo('orders');
    this.wsService.subscribeTo('dispatch');
    this.wsService
      .changes$('order.status_changed', 'delivery.route_updated', 'driver.updated')
      .pipe(debounceTime(500), takeUntilDestroyed())
      .subscribe(() => {
        this.loadRoutes();
        this.loadUnassignedOrders();
        this.refreshSelectedRoute();
      });
  }

  protected readonly routes = signal<RouteResponse[]>([]);
  // Active-only — this backs the trip sheet's driver picker, which must
  // never offer a driver who isn't currently available for a new trip.
  protected readonly drivers = signal<DriverResponse[]>([]);
  // Unfiltered by status — a trip already on the board can reference a
  // driver who has since gone on leave, and that driver's name still has
  // to resolve (not fall back to a raw UUID) wherever the trip is shown.
  protected readonly allDrivers = signal<DriverResponse[]>([]);
  // Drivers themselves carry no name — DriverResponse only has a FK
  // (employee_id) into the Employee record where first_name/last_name
  // actually live, so the driver's display name has to be resolved
  // through this lookup rather than read directly off DriverResponse.
  protected readonly employees = signal<EmployeeResponse[]>([]);
  protected readonly vehicles = signal<VehicleResponse[]>([]);
  // Unfiltered by status, mirroring allDrivers above — a trip already on
  // the board can reference a vehicle now under maintenance.
  protected readonly allVehicles = signal<VehicleResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly scales = signal<ScaleResponse[]>([]);
  protected readonly unassignedOrders = signal<OrderResponse[]>([]);
  // Broader than `unassignedOrders` (not status-filtered) — backs
  // `orderById` below, since an order on a trip is by definition no longer
  // unassigned and would otherwise never resolve.
  private readonly recentOrders = signal<OrderResponse[]>([]);

  protected readonly shortId = shortId;

  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly infoMessage = signal<string | null>(null);

  protected readonly statusColumns = ROUTE_STATUS_COLUMNS;
  protected readonly statusLabel = (status: string) => ROUTE_STATUS_LABELS[status] ?? status;
  protected readonly stopStatusLabel = (status: string) => STOP_STATUS_LABELS[status] ?? status;
  protected readonly statusSeverity = (status: string) =>
    ROUTE_STATUS_SEVERITY[status] ?? 'secondary';

  // ---------------------------------------------------------------------------
  // Filters
  // ---------------------------------------------------------------------------

  protected readonly filterBranchId = signal<string | null>(null);

  protected readonly filterDate = signal<Date | null>(null);

  protected readonly employeeById = computed(() => {
    const map = new Map<string, EmployeeResponse>();
    for (const e of this.employees()) map.set(e.id, e);
    return map;
  });

  private driverDisplayName(driver: DriverResponse): string {
    if (driver.name) return driver.name;
    const employee = this.employeeById().get(driver.employee_id);
    // Falls back to the raw FK only if the employee record hasn't loaded
    // yet (or was deleted) — should be rare, never the normal case.
    return employee ? `${employee.first_name} ${employee.last_name}` : driver.employee_id;
  }

  protected readonly driverNameById = computed(() => {
    const map = new Map<string, string>();
    for (const d of this.allDrivers()) map.set(d.id, this.driverDisplayName(d));
    return map;
  });

  /** Drivers and vans already on a trip that hasn't come back yet — a new
   * trip for them is almost always a mistake (add orders to that trip
   * instead), so the trip sheet offers them disabled. */
  private readonly busyOnTrip = computed(() => {
    const drivers = new Set<string>();
    const vehicles = new Set<string>();
    for (const route of this.routes()) {
      if (!ACTIVE_ROUTE_STATUSES.has(route.status)) continue;
      drivers.add(route.driver_id);
      vehicles.add(route.vehicle_id);
    }
    return { drivers, vehicles };
  });

  protected readonly driverOptions = computed(() =>
    this.drivers().map((d) => {
      const busy = this.busyOnTrip().drivers.has(d.id);
      const name = this.driverDisplayName(d);
      return { id: d.id, label: busy ? `${name} (on a trip)` : name, disabled: busy };
    }),
  );

  protected readonly vehicleNameById = computed(() => {
    const map = new Map<string, string>();
    for (const v of this.allVehicles()) map.set(v.id, this.vehicleDisplayName(v));
    return map;
  });

  private vehicleDisplayName(vehicle: VehicleResponse): string {
    return `${vehicle.make} ${vehicle.model} (${vehicle.registration_number})`;
  }

  protected readonly vehicleOptions = computed(() =>
    this.vehicles().map((v) => {
      const busy = this.busyOnTrip().vehicles.has(v.id);
      const name = this.vehicleDisplayName(v);
      return { id: v.id, label: busy ? `${name} (on a trip)` : name, disabled: busy };
    }),
  );

  protected readonly warehouseNameById = computed(() => {
    const map = new Map<string, string>();
    for (const w of this.warehouses()) map.set(w.id, w.name);
    return map;
  });

  protected readonly cylinderTypeNameById = computed(() => {
    const map = new Map<string, string>();
    for (const c of this.cylinderTypes()) map.set(c.id, c.name);
    return map;
  });

  protected cylinderTypeName(cylinderTypeId: string): string {
    return this.cylinderTypeNameById().get(cylinderTypeId) ?? shortId(cylinderTypeId);
  }

  /** "2 × 14.2 kg, 1 × 19 kg" — what a cash memo carries, at a glance. */
  protected orderCylinders(order: OrderResponse): string {
    return order.lines
      .map((l) => `${l.quantity_ordered} × ${this.cylinderTypeName(l.cylinder_type_id)}`)
      .join(', ');
  }

  /** `/scales` has no server-side warehouse filter, and this screen has no
   * single "selected warehouse" — the load-out weighment step can be logged
   * for any of the tenant's active, certified scales, so the warehouse is
   * shown in the label to disambiguate rather than filtering the list. */
  protected readonly activeScaleOptions = computed(() =>
    this.scales()
      .filter((s) => s.status === 'active')
      .map((s) => ({
        id: s.id,
        label: `${s.asset_tag} — ${this.warehouseNameById().get(s.warehouse_id) ?? 'Unknown warehouse'}`,
      })),
  );

  protected readonly routesByStatus = computed(() => {
    const map = new Map<string, RouteResponse[]>();
    for (const status of ROUTE_STATUS_COLUMNS) map.set(status, []);
    for (const route of this.routes()) {
      const bucket = map.get(route.status);
      if (bucket) bucket.push(route);
      else map.set(route.status, [route]);
    }
    return map;
  });

  protected readonly fieldMessages = {
    actual_amount: { required: 'Enter the amount handed over.', min: 'Cannot be negative.' },
    cylinder_type_id: { required: 'Select a cylinder type.' },
    scale_id: { required: 'Select a certified scale.' },
    total_cylinders: {
      required: 'Enter how many cylinders were checked.',
      min: 'Must be at least 1.',
    },
    underweight_cylinder_count: {
      required: 'Enter the underweight count (0 if none).',
      min: 'Cannot be negative.',
    },
  };

  // ---------------------------------------------------------------------------
  // Trip sheet drawer
  //
  // How a distributor's godown actually dispatches: pick the delivery man
  // and van, tick the cash memos (confirmed orders) going out, issue the
  // cylinders those need against godown stock, and send the van. One
  // `POST /routes/{id}/load-and-dispatch` does the stock transfer, the
  // order assignment and the release to the driver together. Opened either
  // for a new trip or for an existing one that hasn't left yet (top-up).
  // ---------------------------------------------------------------------------

  protected readonly showTripSheet = signal(false);
  protected readonly newTripTrigger = viewChild<ElementRef<HTMLButtonElement>>('newTripTriggerEl');
  /** The trip being loaded; null while it's a new one not yet created. */
  protected readonly tripRoute = signal<RouteResponse | null>(null);
  protected readonly tripBranchId = signal<string | null>(null);
  protected readonly tripDriverId = signal<string | null>(null);
  protected readonly tripVehicleId = signal<string | null>(null);
  protected readonly tripDate = signal<Date>(new Date());
  protected readonly tripWarehouseId = signal<string | null>(null);
  protected readonly tripOrderIds = signal<ReadonlySet<string>>(new Set());
  protected readonly tripSpares = signal<Readonly<Record<string, number>>>({});
  protected readonly tripError = signal<string | null>(null);
  /** Filled cylinders per type — loaded when the godown/van is picked. */
  private readonly godownStock = signal<ReadonlyMap<string, number> | null>(null);
  private readonly vanStock = signal<ReadonlyMap<string, number>>(new Map());

  protected readonly tripVehicle = computed(
    () => this.allVehicles().find((v) => v.id === this.tripVehicleId()) ?? null,
  );

  /** The trip branch's own godowns; every godown only when that branch has
   * none (a branch supplied from a shared depot). */
  protected readonly tripWarehouseOptions = computed(() => {
    const inBranch = this.branchWarehouses();
    return inBranch.length > 0 ? inBranch : this.warehouses();
  });

  private readonly branchWarehouses = computed(() => {
    const branchId = this.tripBranchId();
    return branchId ? this.warehouses().filter((w) => w.branch_id === branchId) : [];
  });

  /** Pre-selected godown: the trip branch's own, never another branch's. */
  private defaultTripWarehouseId(): string | null {
    return this.branchWarehouses()[0]?.id ?? null;
  }

  /** Confirmed orders not on any trip yet, for this trip's branch. */
  protected readonly tripCandidateOrders = computed(() => {
    const branchId = this.tripBranchId();
    return this.unassignedOrders().filter((o) => !branchId || o.branch_id === branchId);
  });

  /** Orders already on the trip that haven't left yet — the load-and-
   * dispatch call always includes them and loads any backorder they carry. */
  protected readonly tripWaitingOrders = computed(() => {
    const route = this.tripRoute();
    if (!route) return [];
    const pending = new Set(
      (route.stops ?? []).filter((s) => s.status === 'pending').map((s) => s.order_id),
    );
    return this.recentOrders().filter(
      (o) => pending.has(o.id) && (o.status === 'assigned' || o.status === 'ready_for_dispatch'),
    );
  });

  /** One row per cylinder type: the same arithmetic the server does. */
  protected readonly loadSheet = computed(() => {
    const needed = new Map<string, number>();
    const add = (id: string, qty: number) => needed.set(id, (needed.get(id) ?? 0) + qty);
    for (const order of this.tripWaitingOrders()) {
      for (const line of order.lines) add(line.cylinder_type_id, line.quantity_pending);
    }
    const picked = this.tripOrderIds();
    for (const order of this.tripCandidateOrders()) {
      if (!picked.has(order.id)) continue;
      for (const line of order.lines) add(line.cylinder_type_id, line.quantity_ordered);
    }
    const spares = this.tripSpares();
    const godown = this.godownStock();
    const van = this.vanStock();
    return this.cylinderTypes()
      .filter((c) => c.is_active || needed.has(c.id))
      .map((c) => {
        const forOrders = needed.get(c.id) ?? 0;
        const onVan = van.get(c.id) ?? 0;
        const spare = spares[c.id] ?? 0;
        const toLoad = Math.max(0, forOrders - onVan) + spare;
        const inGodown = godown ? (godown.get(c.id) ?? 0) : null;
        return {
          id: c.id,
          name: c.name,
          forOrders,
          onVan,
          spare,
          toLoad,
          inGodown,
          short: inGodown !== null && toLoad > inGodown,
        };
      });
  });

  protected readonly tripShort = computed(() => this.loadSheet().some((row) => row.short));

  protected readonly tripTotals = computed(() => {
    const rows = this.loadSheet();
    const toLoad = rows.reduce((sum, row) => sum + row.toLoad, 0);
    const onVanAfter = rows.reduce((sum, row) => sum + row.onVan + row.toLoad, 0);
    return { toLoad, onVanAfter };
  });

  protected readonly tripOverCapacity = computed(() => {
    const vehicle = this.tripVehicle();
    return !!vehicle && this.tripTotals().onVanAfter > vehicle.capacity_units;
  });

  protected readonly tripOrderCount = computed(
    () => this.tripOrderIds().size + this.tripWaitingOrders().length,
  );

  protected readonly canSubmitTrip = computed(
    () =>
      !this.loading() &&
      !!this.tripBranchId() &&
      !!this.tripDriverId() &&
      !!this.tripVehicleId() &&
      !!this.tripWarehouseId() &&
      this.tripOrderCount() > 0 &&
      !this.tripShort(),
  );

  protected openNewTrip(preselectOrder?: OrderResponse): void {
    const branchId =
      preselectOrder?.branch_id ??
      this.filterBranchId() ??
      this.authTokenStore.defaultBranchIdAmong(this.branches());
    this.tripRoute.set(null);
    this.tripBranchId.set(branchId ?? null);
    this.tripDriverId.set(null);
    this.tripVehicleId.set(null);
    this.tripDate.set(new Date());
    this.tripOrderIds.set(new Set(preselectOrder ? [preselectOrder.id] : []));
    this.tripSpares.set({});
    this.tripError.set(null);
    this.vanStock.set(new Map());
    this.onTripWarehouseChange(this.defaultTripWarehouseId());
    this.showTripSheet.set(true);
  }

  protected openTripSheetFor(route: RouteResponse): void {
    this.tripRoute.set(route);
    this.tripBranchId.set(route.branch_id);
    this.tripDriverId.set(route.driver_id);
    this.tripVehicleId.set(route.vehicle_id);
    this.tripDate.set(new Date(route.date));
    this.tripOrderIds.set(new Set());
    this.tripSpares.set({});
    this.tripError.set(null);
    this.loadVanStock(route.vehicle_id);
    this.onTripWarehouseChange(this.defaultTripWarehouseId());
    this.showRouteDetail.set(false);
    this.showTripSheet.set(true);
  }

  protected onTripDriverChange(driverId: string | null): void {
    this.tripDriverId.set(driverId);
    // A delivery man works out of one branch; the trip follows him.
    const driver = this.drivers().find((d) => d.id === driverId);
    if (driver && driver.branch_id !== this.tripBranchId()) {
      this.onTripBranchChange(driver.branch_id);
    }
  }

  protected onTripBranchChange(branchId: string | null): void {
    this.tripBranchId.set(branchId);
    this.tripOrderIds.set(new Set());
    this.onTripWarehouseChange(this.defaultTripWarehouseId());
  }

  protected onTripVehicleChange(vehicleId: string | null): void {
    this.tripVehicleId.set(vehicleId);
    if (vehicleId) this.loadVanStock(vehicleId);
    else this.vanStock.set(new Map());
  }

  protected onTripWarehouseChange(warehouseId: string | null): void {
    this.tripWarehouseId.set(warehouseId);
    this.godownStock.set(null);
    if (!warehouseId) return;
    this.inventoryService.getBalance('warehouse', warehouseId).subscribe({
      next: (balance) => this.godownStock.set(filledStock(balance.balances)),
      // Stock is a guide here; the server still refuses a short load.
      error: () => this.godownStock.set(null),
    });
  }

  private loadVanStock(vehicleId: string): void {
    this.vanStock.set(new Map());
    this.inventoryService.getBalance('vehicle', vehicleId).subscribe({
      next: (balance) => this.vanStock.set(filledStock(balance.balances)),
    });
  }

  protected isTripOrderPicked(orderId: string): boolean {
    return this.tripOrderIds().has(orderId);
  }

  protected toggleTripOrder(orderId: string, picked: boolean): void {
    const next = new Set(this.tripOrderIds());
    if (picked) next.add(orderId);
    else next.delete(orderId);
    this.tripOrderIds.set(next);
  }

  protected toggleAllTripOrders(picked: boolean): void {
    this.tripOrderIds.set(new Set(picked ? this.tripCandidateOrders().map((o) => o.id) : []));
  }

  protected setTripSpare(cylinderTypeId: string, quantity: number | null): void {
    this.tripSpares.set({ ...this.tripSpares(), [cylinderTypeId]: Math.max(0, quantity ?? 0) });
  }

  protected onSubmitTrip(): void {
    if (!this.canSubmitTrip()) return;
    this.loading.set(true);
    this.tripError.set(null);
    const existing = this.tripRoute();
    if (existing) {
      this.dispatchTrip(existing);
      return;
    }
    this.deliveryService
      .planRoute({
        branch_id: this.tripBranchId() as string,
        driver_id: this.tripDriverId() as string,
        vehicle_id: this.tripVehicleId() as string,
        route_date: this.tripDate().toISOString(),
      })
      .subscribe({
        next: (route) => {
          // Kept so a retry after a failed load reuses this trip.
          this.tripRoute.set(route);
          this.dispatchTrip(route);
        },
        error: (err) => {
          this.tripError.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  private dispatchTrip(route: RouteResponse): void {
    const spares = this.tripSpares();
    this.deliveryService
      .loadAndDispatchRoute(route.id, {
        warehouse_id: this.tripWarehouseId() as string,
        order_ids: [...this.tripOrderIds()],
        extra_lines: Object.entries(spares)
          .filter(([, quantity]) => quantity > 0)
          .map(([cylinder_type_id, quantity]) => ({ cylinder_type_id, quantity })),
      })
      .subscribe({
        next: () => {
          this.showTripSheet.set(false);
          this.refreshAfterMutation(
            `Trip dispatched for ${this.driverNameById().get(route.driver_id) ?? 'the driver'}.`,
          );
        },
        error: (err) => {
          this.tripError.set(errorMessageFor(err));
          this.loading.set(false);
          // A new trip was created even though loading failed; show it.
          this.loadRoutes();
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Trip detail drawer
  // ---------------------------------------------------------------------------

  protected readonly selectedRoute = signal<RouteResponse | null>(null);
  protected readonly showRouteDetail = signal(false);

  protected readonly canLoadAndDispatch = computed(
    () => this.selectedRoute()?.status === 'planned',
  );
  protected readonly canAddOrders = computed(() => this.selectedRoute()?.status === 'loaded');
  protected readonly canCancelRoute = computed(() => {
    const status = this.selectedRoute()?.status;
    return !!status && CANCELLABLE_ROUTE_STATUSES.has(status);
  });
  // AI Operational Intelligence, Horizon 1 Stage 5 — same planned/loaded
  // gate as adding orders (`Route.resequence_stops()`'s own guard), plus a
  // minimum of 3 pending stops: reordering 1-2 stops has nothing to
  // optimize, so the button stays hidden rather than offering a no-op.
  protected readonly canOptimizeSelectedRoute = computed(() => {
    const route = this.selectedRoute();
    if (!route || (route.status !== 'planned' && route.status !== 'loaded')) return false;
    const pendingStops = (route.stops ?? []).filter((s) => s.status === 'pending');
    return pendingStops.length >= 3;
  });
  protected readonly canReconcileRoute = computed(
    () => this.selectedRoute()?.status === 'completed',
  );
  // Declaring the cash collected only makes sense once a trip has actually
  // run — same condition as Reconcile, which also only applies post-completion.
  protected readonly canDeclareCashHandover = computed(
    () => this.selectedRoute()?.status === 'completed',
  );

  // ---------------------------------------------------------------------------
  // Log Load-Out Weighment (inline sub-form within the trip detail drawer)
  //
  // MDG 2022 cl. 1.4(c)(d) — 100% of cylinders checked before dispatch. A
  // tenant that has opted into the gate (`weighment_gate_enabled`) needs a
  // passing record per cylinder type *before* the load will succeed
  // (Weighment Part 3), so it is logged ahead of loading. One record per
  // cylinder type, so the sub-form stays open after each save to let staff
  // work through the whole manifest.
  // ---------------------------------------------------------------------------

  protected readonly showLoadOutWeighmentForm = signal(false);
  protected readonly routeWeighments = signal<WeighmentRecordResponse[]>([]);
  protected readonly loadOutWeighmentForm = this.fb.group({
    cylinder_type_id: ['', [Validators.required]],
    scale_id: ['', [Validators.required]],
    total_cylinders: [1, [Validators.required, Validators.min(1)]],
    underweight_cylinder_count: [0, [Validators.required, Validators.min(0)]],
  });

  protected openLoadOutWeighmentForm(): void {
    const route = this.selectedRoute();
    if (!route) return;
    this.loadOutWeighmentForm.reset({
      cylinder_type_id: '',
      scale_id: this.activeScaleOptions()[0]?.id ?? '',
      total_cylinders: 1,
      underweight_cylinder_count: 0,
    });
    this.weighmentService.listRouteWeighments(route.id).subscribe({
      next: (res) => this.routeWeighments.set(res.items),
    });
    this.showLoadOutWeighmentForm.set(true);
  }

  protected onSubmitLoadOutWeighment(): void {
    const route = this.selectedRoute();
    if (!route || this.loadOutWeighmentForm.invalid) return;
    const val = this.loadOutWeighmentForm.getRawValue();
    this.loading.set(true);
    this.weighmentService
      .recordRouteLoadOutWeighment(route.id, {
        scale_id: val.scale_id,
        cylinder_type_id: val.cylinder_type_id,
        total_cylinders_in_batch: val.total_cylinders,
        cylinders_checked: val.total_cylinders,
        underweight_cylinder_count: val.underweight_cylinder_count,
      })
      .subscribe({
        next: (record) => {
          this.routeWeighments.set([...this.routeWeighments(), record]);
          this.loadOutWeighmentForm.patchValue({
            cylinder_type_id: '',
            total_cylinders: 1,
            underweight_cylinder_count: 0,
          });
          this.infoMessage.set('Weighment recorded.');
          this.errorMessage.set(null);
          this.loading.set(false);
          this.notify.success('Weighment recorded.');
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Declare Cash Handover (inline sub-form within the trip detail drawer)
  // ---------------------------------------------------------------------------

  protected readonly showCashHandoverForm = signal(false);
  protected readonly lastCashHandover = signal<CashHandoverResponse | null>(null);
  protected readonly cashHandoverForm = this.fb.group({
    actual_amount: [0, [Validators.required, Validators.min(0)]],
  });

  /** `RouteStopResponse` only carries `order_id`, not the full `Order`
   * object — this map lets a stop card show the order number and address
   * without a backend join. Falls back to `shortId` for a stop whose order
   * isn't among the recently loaded orders. */
  protected readonly orderById = computed(() => {
    const map = new Map<string, OrderResponse>();
    for (const o of this.recentOrders()) map.set(o.id, o);
    return map;
  });

  // ---------------------------------------------------------------------------
  // Init / loaders
  // ---------------------------------------------------------------------------

  ngOnInit(): void {
    this.branchService.listBranches().subscribe({
      next: (branches) => this.branches.set(branches),
      error: () => this.errorMessage.set('Failed to load branches.'),
    });
    this.warehouseService.listWarehouses().subscribe({
      next: (warehouses) => this.warehouses.set(warehouses),
      error: () => this.errorMessage.set('Failed to load godowns.'),
    });
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (types) => this.cylinderTypes.set(types),
      error: () => this.errorMessage.set('Failed to load cylinder types.'),
    });
    // `/scales` needs `weighment:record`; a role without it (e.g. a
    // dispatcher) would only get a 403 — skip the call (DO-31).
    if (this.authService.principal()?.permissions.has('weighment:record')) {
      this.weighmentService.listScales({ status: 'active', limit: 200 }).subscribe({
        next: (res) => this.scales.set(res.items),
      });
    }
    this.loadDriversAndVehicles();
    this.loadRoutes();
    this.loadUnassignedOrders();
  }

  protected loadDriversAndVehicles(): void {
    this.deliveryService.listDrivers(0, 200, undefined, 'active').subscribe({
      next: (page) => this.drivers.set(page.items),
      error: () => this.errorMessage.set('Failed to load drivers.'),
    });
    this.deliveryService.listDrivers(0, 200).subscribe({
      next: (page) => this.allDrivers.set(page.items),
      error: () => this.errorMessage.set('Failed to load drivers.'),
    });
    this.employeeService.listEmployees({ limit: 200, role: 'driver' }).subscribe({
      next: (page) => this.employees.set(page.items),
      error: () => this.errorMessage.set('Failed to load driver names.'),
    });
    this.deliveryService.listVehicles(0, 200, undefined, 'active').subscribe({
      next: (page) => this.vehicles.set(page.items),
      error: () => this.errorMessage.set('Failed to load vehicles.'),
    });
    this.deliveryService.listVehicles(0, 200).subscribe({
      next: (page) => this.allVehicles.set(page.items),
      error: () => this.errorMessage.set('Failed to load vehicles.'),
    });
  }

  /** Re-reads the board — trips, the orders waiting for one, and driver/van
   * availability. Public so a realtime event (DO-24) can trigger it. */
  reload(): void {
    this.loadRoutes();
    this.loadUnassignedOrders();
    this.loadDriversAndVehicles();
  }

  protected loadRoutes(): void {
    this.loading.set(true);
    const branchId = this.filterBranchId() ?? undefined;
    const date = this.filterDate();
    const dateStr = date ? toDateOnlyString(date) : undefined;
    this.deliveryService.listRoutes(1, 100, undefined, branchId, dateStr, dateStr).subscribe({
      next: (page) => {
        this.routes.set(page.items);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected onFilterBranchChange(branchId: string | null): void {
    this.filterBranchId.set(branchId);
    this.loadRoutes();
  }

  protected onFilterDateChange(date: Date | null): void {
    this.filterDate.set(date);
    this.loadRoutes();
  }

  protected loadUnassignedOrders(): void {
    // No backend query filter for "unassigned" exists (`route_stop_id` isn't
    // a listOrders filter) — fetch recent orders (no status filter, so
    // `recentOrders`/`orderById` also cover ones already on a trip) and
    // derive the confirmed-and-unassigned subset client-side.
    this.orderService.listOrders({ limit: 200 }).subscribe({
      next: (page) => {
        this.recentOrders.set(page.items);
        this.unassignedOrders.set(
          page.items.filter((o) => o.status === 'confirmed' && o.route_stop_id == null),
        );
      },
      error: (err) => this.errorMessage.set(errorMessageFor(err)),
    });
  }

  private refreshAfterMutation(message: string): void {
    this.infoMessage.set(message);
    this.errorMessage.set(null);
    this.loading.set(false);
    this.notify.success(message);
    this.loadRoutes();
    this.loadUnassignedOrders();
  }

  // ---------------------------------------------------------------------------
  // Trip detail
  // ---------------------------------------------------------------------------

  protected openRouteDetail(route: RouteResponse): void {
    this.showLoadOutWeighmentForm.set(false);
    this.showCashHandoverForm.set(false);
    this.lastCashHandover.set(null);
    this.showRouteDetail.set(true);
    this.loading.set(true);
    this.deliveryService.getRoute(route.id).subscribe({
      next: (full) => {
        this.selectedRoute.set(full);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  private refreshSelectedRoute(): void {
    const routeId = this.selectedRoute()?.id;
    if (!routeId) return;
    this.deliveryService.getRoute(routeId).subscribe({
      next: (full) => this.selectedRoute.set(full),
    });
  }

  protected onCancelRoute(): void {
    const route = this.selectedRoute();
    if (!route) return;
    this.loading.set(true);
    this.deliveryService.updateRouteStatus(route.id, 'cancelled').subscribe({
      next: () => {
        this.refreshSelectedRoute();
        this.refreshAfterMutation('Trip cancelled.');
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected onOptimizeRoute(): void {
    const route = this.selectedRoute();
    if (!route) return;
    this.loading.set(true);
    this.deliveryService.optimizeRoute(route.id).subscribe({
      next: (result) => {
        this.selectedRoute.set(result.route);
        const saved = result.km_saved;
        const message =
          saved > 0.05
            ? `Stop order optimised — ~${saved.toFixed(1)} km saved.`
            : 'Stop order optimised — already close to optimal.';
        this.refreshAfterMutation(message);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected onReconcileRoute(): void {
    const route = this.selectedRoute();
    if (!route) return;
    this.loading.set(true);
    this.deliveryService.completeRouteReconciliation(route.id).subscribe({
      next: () => {
        this.refreshSelectedRoute();
        this.refreshAfterMutation('Trip settled.');
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected goToInventoryReconciliation(): void {
    void this.router.navigate(['/inventory']);
  }

  protected openCashHandoverForm(): void {
    this.lastCashHandover.set(null);
    this.cashHandoverForm.reset({ actual_amount: 0 });
    this.showCashHandoverForm.set(true);
  }

  protected onSubmitCashHandover(): void {
    const route = this.selectedRoute();
    if (!route || this.cashHandoverForm.invalid) return;
    const { actual_amount } = this.cashHandoverForm.getRawValue();
    this.loading.set(true);
    this.deliveryService
      .declareCashHandover({
        driver_id: route.driver_id,
        route_id: route.id,
        actual_amount,
      })
      .subscribe({
        next: (handover) => {
          this.lastCashHandover.set(handover);
          this.showCashHandoverForm.set(false);
          this.infoMessage.set('Cash handover declared.');
          this.errorMessage.set(null);
          this.loading.set(false);
          this.notify.success('Cash handover declared.');
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }
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
