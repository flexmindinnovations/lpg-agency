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
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { Button, ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { InputNumber } from 'primeng/inputnumber';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { DatePicker } from 'primeng/datepicker';
import { Tooltip } from 'primeng/tooltip';
import {
  AdminBranchService,
  AdminCylinderTypeService,
  AdminWarehouseService,
  DeliveryService,
  OrderService,
  type AppError,
  type BranchResponse,
  type CylinderTypeResponse,
  type DriverResponse,
  type OrderResponse,
  type RouteResponse,
  type VehicleResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';

const ROUTE_STATUS_COLUMNS = [
  'planned',
  'loaded',
  'in_progress',
  'completed',
  'reconciled',
  'cancelled',
] as const;

const ROUTE_STATUS_LABELS: Record<string, string> = {
  planned: 'Planned',
  loaded: 'Loaded',
  in_progress: 'In Progress',
  completed: 'Completed',
  reconciled: 'Reconciled',
  cancelled: 'Cancelled',
};

const ROUTE_STATUS_SEVERITY: Record<
  string,
  'success' | 'info' | 'warn' | 'danger' | 'secondary'
> = {
  planned: 'secondary',
  loaded: 'info',
  in_progress: 'warn',
  completed: 'success',
  reconciled: 'success',
  cancelled: 'danger',
};

/** Routes can only be cancelled while still `planned` or `loaded` (see
 * `RouteStatus` transition table in `domain/delivery/route.py`) — once a
 * route is `in_progress` it has to run to completion. */
const CANCELLABLE_ROUTE_STATUSES = new Set(['planned', 'loaded']);

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    case 'ROUTE_RECONCILIATION_PENDING':
      return "This route's vehicle needs an approved reconciliation before it can be closed out. Approve one from Inventory first.";
    case 'RESOURCE_NOT_FOUND':
      return isAppError(error) && error.detail ? error.detail : 'That resource could not be found.';
    case 'INVALID_STATE_TRANSITION':
      return 'That action is not valid for the route in its current state.';
    default:
      return 'Something went wrong. Please try again.';
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
    DatePipe,
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    Button,
    Drawer,
    InputNumber,
    Message,
    Select,
    Tag,
    DatePicker,
    Tooltip,
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
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly router = inject(Router);

  protected readonly routes = signal<RouteResponse[]>([]);
  protected readonly drivers = signal<DriverResponse[]>([]);
  protected readonly vehicles = signal<VehicleResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly unassignedOrders = signal<OrderResponse[]>([]);

  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly infoMessage = signal<string | null>(null);

  protected readonly statusColumns = ROUTE_STATUS_COLUMNS;
  protected readonly statusLabel = (status: string) => ROUTE_STATUS_LABELS[status] ?? status;
  protected readonly statusSeverity = (status: string) =>
    ROUTE_STATUS_SEVERITY[status] ?? 'secondary';

  // ---------------------------------------------------------------------------
  // Filters
  // ---------------------------------------------------------------------------

  protected readonly filterBranchId = signal<string | null>(null);
  protected readonly filterDate = signal<Date | null>(null);

  protected readonly driverNameById = computed(() => {
    const map = new Map<string, string>();
    for (const d of this.drivers()) map.set(d.id, d.employee_code);
    return map;
  });

  protected readonly vehicleNameById = computed(() => {
    const map = new Map<string, string>();
    for (const v of this.vehicles()) map.set(v.id, v.registration_number);
    return map;
  });

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

  /** Only `planned`/`loaded` routes are valid targets for assigning an order. */
  protected readonly assignableRoutes = computed(() =>
    this.routes().filter((r) => r.status === 'planned' || r.status === 'loaded'),
  );

  protected readonly assignableRouteOptions = computed(() =>
    this.assignableRoutes().map((r) => ({
      id: r.id,
      label: `${r.date.slice(0, 10)} — ${this.driverNameById().get(r.driver_id) ?? r.driver_id} (${this.statusLabel(r.status)})`,
    })),
  );

  // ---------------------------------------------------------------------------
  // Plan Route drawer
  // ---------------------------------------------------------------------------

  protected readonly showPlanModal = signal(false);
  protected readonly planTrigger = viewChild<ElementRef<HTMLButtonElement>>('planTriggerEl');

  protected readonly planForm = this.fb.group({
    branch_id: ['', [Validators.required]],
    driver_id: ['', [Validators.required]],
    vehicle_id: ['', [Validators.required]],
    date: [new Date(), [Validators.required]],
  });

  // ---------------------------------------------------------------------------
  // Route Detail drawer (+ inline Load Vehicle sub-form)
  // ---------------------------------------------------------------------------

  protected readonly selectedRoute = signal<RouteResponse | null>(null);
  protected readonly showRouteDetail = signal(false);
  protected readonly showLoadForm = signal(false);

  protected readonly canStartRoute = computed(() => this.selectedRoute()?.status === 'loaded');
  protected readonly canCancelRoute = computed(() => {
    const status = this.selectedRoute()?.status;
    return !!status && CANCELLABLE_ROUTE_STATUSES.has(status);
  });
  protected readonly canLoadRoute = computed(() => this.selectedRoute()?.status === 'planned');
  protected readonly canReconcileRoute = computed(
    () => this.selectedRoute()?.status === 'completed',
  );

  protected readonly loadForm = this.fb.group({
    warehouse_id: ['', [Validators.required]],
    lines: this.fb.array<ReturnType<typeof this.buildLoadLineGroup>>([]),
  });

  private buildLoadLineGroup() {
    return this.fb.group({
      cylinder_type_id: ['', [Validators.required]],
      quantity: [1, [Validators.required, Validators.min(1)]],
    });
  }

  protected get loadLines() {
    return this.loadForm.controls.lines;
  }

  // ---------------------------------------------------------------------------
  // Assign order to route drawer
  // ---------------------------------------------------------------------------

  protected readonly showAssignOrderDrawer = signal(false);
  protected readonly selectedOrderForAssign = signal<OrderResponse | null>(null);
  protected readonly assignOrderForm = this.fb.group({
    route_id: ['', [Validators.required]],
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
      error: () => this.errorMessage.set('Failed to load warehouses.'),
    });
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (types) => this.cylinderTypes.set(types),
      error: () => this.errorMessage.set('Failed to load cylinder types.'),
    });
    this.loadDriversAndVehicles();
    this.loadRoutes();
    this.loadUnassignedOrders();
  }

  protected loadDriversAndVehicles(): void {
    this.deliveryService.listDrivers(0, 200, undefined, 'active').subscribe({
      next: (page) => this.drivers.set(page.items),
      error: () => this.errorMessage.set('Failed to load drivers.'),
    });
    this.deliveryService.listVehicles(0, 200, undefined, 'active').subscribe({
      next: (page) => this.vehicles.set(page.items),
      error: () => this.errorMessage.set('Failed to load vehicles.'),
    });
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
    // a listOrders filter) — fetch confirmed orders and filter client-side.
    this.orderService.listOrders({ status: 'confirmed', limit: 100 }).subscribe({
      next: (page) => {
        this.unassignedOrders.set(page.items.filter((o) => o.route_stop_id == null));
      },
      error: (err) => this.errorMessage.set(errorMessageFor(err)),
    });
  }

  private refreshAfterMutation(message: string): void {
    this.infoMessage.set(message);
    this.errorMessage.set(null);
    this.loading.set(false);
    this.loadRoutes();
    this.loadUnassignedOrders();
  }

  // ---------------------------------------------------------------------------
  // Plan Route
  // ---------------------------------------------------------------------------

  protected openPlanModal(): void {
    this.planForm.reset({
      branch_id: '',
      driver_id: this.drivers().length > 0 ? this.drivers()[0].id : '',
      vehicle_id: this.vehicles().length > 0 ? this.vehicles()[0].id : '',
      date: new Date(),
    });
    this.showPlanModal.set(true);
  }

  protected onSubmitPlan(): void {
    if (this.planForm.invalid) return;

    const val = this.planForm.getRawValue();
    this.loading.set(true);
    this.deliveryService
      .planRoute({
        branch_id: val.branch_id,
        driver_id: val.driver_id,
        vehicle_id: val.vehicle_id,
        route_date: val.date.toISOString(),
      })
      .subscribe({
        next: () => {
          this.showPlanModal.set(false);
          this.refreshAfterMutation('Route planned.');
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Route Detail
  // ---------------------------------------------------------------------------

  protected openRouteDetail(route: RouteResponse): void {
    this.showLoadForm.set(false);
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

  protected onStartRoute(): void {
    const route = this.selectedRoute();
    if (!route) return;
    this.loading.set(true);
    this.deliveryService.updateRouteStatus(route.id, 'in_progress').subscribe({
      next: () => {
        this.refreshSelectedRoute();
        this.refreshAfterMutation('Route started.');
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected onCancelRoute(): void {
    const route = this.selectedRoute();
    if (!route) return;
    this.loading.set(true);
    this.deliveryService.updateRouteStatus(route.id, 'cancelled').subscribe({
      next: () => {
        this.refreshSelectedRoute();
        this.refreshAfterMutation('Route cancelled.');
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
        this.refreshAfterMutation('Route reconciled.');
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

  // ---------------------------------------------------------------------------
  // Load Vehicle (inline sub-form within the Route Detail drawer)
  // ---------------------------------------------------------------------------

  protected openLoadForm(): void {
    this.loadForm.reset({ warehouse_id: this.warehouses()[0]?.id ?? '' });
    this.loadLines.clear();
    this.loadLines.push(this.buildLoadLineGroup());
    this.showLoadForm.set(true);
  }

  protected addLoadLine(): void {
    this.loadLines.push(this.buildLoadLineGroup());
  }

  protected removeLoadLine(index: number): void {
    if (this.loadLines.length > 1) this.loadLines.removeAt(index);
  }

  protected onSubmitLoad(): void {
    const route = this.selectedRoute();
    if (!route || this.loadForm.invalid) return;
    const val = this.loadForm.getRawValue();
    this.loading.set(true);
    this.deliveryService
      .loadVehicleForRoute(route.id, {
        warehouse_id: val.warehouse_id,
        lines: val.lines.map((line) => ({
          cylinder_type_id: line.cylinder_type_id,
          quantity: line.quantity,
        })),
      })
      .subscribe({
        next: () => {
          this.showLoadForm.set(false);
          this.refreshSelectedRoute();
          this.refreshAfterMutation('Vehicle loaded.');
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }

  // ---------------------------------------------------------------------------
  // Assign order to route
  // ---------------------------------------------------------------------------

  protected openAssignOrderDrawer(order: OrderResponse): void {
    this.selectedOrderForAssign.set(order);
    this.assignOrderForm.reset({ route_id: this.assignableRoutes()[0]?.id ?? '' });
    this.showAssignOrderDrawer.set(true);
  }

  protected onSubmitAssignOrder(): void {
    const order = this.selectedOrderForAssign();
    if (!order || this.assignOrderForm.invalid) return;
    const { route_id } = this.assignOrderForm.getRawValue();
    this.loading.set(true);
    this.deliveryService.assignOrderToRoute(route_id, order.id).subscribe({
      next: () => {
        this.showAssignOrderDrawer.set(false);
        this.selectedOrderForAssign.set(null);
        this.refreshAfterMutation('Order assigned to route.');
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }
}
