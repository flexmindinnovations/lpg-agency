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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  FormsModule,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { debounceTime } from 'rxjs';
import { ButtonDirective } from 'primeng/button';
import { DatePicker } from 'primeng/datepicker';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { InputNumber } from 'primeng/inputnumber';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import {
  OrderService,
  WebSocketService,
  type OrderStatusValue,
  type CustomerAddressResponse,
  type CustomerResponse,
  type OrderableCylinderTypeResponse,
  type OrderResponse,
} from '@lpg/shared/data-access';
import {
  DataGridComponent,
  type DataGridColumn,
  FormFieldComponent,
  HasPermissionDirective,
  PageHeaderComponent,
  BOOKING_SOURCE_LABELS,
  EmptyStateComponent,
  StatusChipCell,
  formatCurrencyInr,
  formatReportDate,
  shortId,
} from '@lpg/shared/ui';
import { InputText } from 'primeng/inputtext';
import { Subject } from 'rxjs';
import { CustomerAutocomplete } from '../customer-autocomplete/customer-autocomplete';
import {
  DATE_INPUT_FORMAT,
  DATE_INPUT_PLACEHOLDER,
  STATUS_LABELS,
  deliveryDayIso,
  STATUS_SEVERITY,
  endOfLocalDayIso,
  errorMessageFor,
  startOfLocalDayIso,
} from '../order-status.util';

const STATUS_OPTIONS = (
  [
    'booked',
    'confirmed',
    'assigned',
    'ready_for_dispatch',
    'out_for_delivery',
    'failed_delivery',
    'delivered',
    'cancelled',
    'closed',
  ] as const
).map((value) => ({ value, label: STATUS_LABELS[value] }));

/** A typed search term only, never a half-typed string, counts as a customer. */
function isCustomer(value: unknown): value is CustomerResponse {
  return typeof value === 'object' && value !== null && 'id' in value;
}

// What staff can record on a dashboard booking. The server fills in `staff` ("Dashboard") when
// nothing is chosen and sets `mobile_app` itself for the Customer App, so neither a staff user
// nor the form can claim it; `api` is for integrations, not people.
const BOOKING_SOURCE_OPTIONS = (['staff', 'phone', 'walk_in', 'whatsapp'] as const).map(
  (value) => ({
    value,
    label: BOOKING_SOURCE_LABELS[value],
  }),
);

@Component({
  selector: 'lpg-order-queue',
  standalone: true,
  imports: [
    PageHeaderComponent,
    HeaderTitlePortalDirective,
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    Drawer,
    DrawerA11yDirective,
    Message,
    Select,
    InputNumber,
    DatePicker,
    DataGridComponent,
    CustomerAutocomplete,
    FormFieldComponent,
    HasPermissionDirective,
    EmptyStateComponent,
    InputText,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './order-queue.html',
  styleUrl: './order-queue.css',
})
export class OrderQueue implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly orderService = inject(OrderService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly wsService = inject(WebSocketService);

  constructor() {
    // Live-refresh the list when any order in the tenant changes state
    // (new booking, confirmation, delivery, cancellation). Debounced so a
    // burst — e.g. a bulk cancel — triggers one refetch, and silent so it
    // doesn't flash the loading spinner over a populated grid.
    this.wsService.subscribeTo('orders');
    this.wsService
      .on('order.status_changed')
      .pipe(debounceTime(500), takeUntilDestroyed())
      .subscribe(() => this.loadOrders({ silent: true }));

    // The customer is a real form control now (`lpg-customer-autocomplete` is
    // a CVA); mirror it into the signal the address-dependent template blocks
    // read, and clear the address whenever the customer changes.
    // While the user is still typing, the control holds the search text,
    // not a customer: nothing is loaded and no error shows until a customer
    // is actually picked (DO-09).
    this.createForm.controls.customer.valueChanges.pipe(takeUntilDestroyed()).subscribe((value) => {
      const customer = isCustomer(value) ? value : null;
      if (customer?.id === this.selectedCustomer()?.id) return;
      this.selectedCustomer.set(customer);
      this.selectedAddress.set(null);
      this.createForm.controls.address_id.setValue('');
      this.loadOrderableCylinderTypes(customer);
      if (customer) this.preselectAddress(customer);
    });

    this.searchChanges
      .pipe(debounceTime(350), takeUntilDestroyed())
      .subscribe(() => this.loadOrders());
  }

  private readonly searchChanges = new Subject<void>();
  protected readonly searchText = signal('');
  protected readonly dateRange = signal<Date[] | null>(null);
  protected readonly dateInputFormat = DATE_INPUT_FORMAT;
  protected readonly today = new Date(new Date().setHours(0, 0, 0, 0));
  protected readonly dateInputPlaceholder = DATE_INPUT_PLACEHOLDER;
  protected readonly hasFilters = computed(
    () => !!this.statusFilter() || !!this.searchText().trim() || !!this.dateRange()?.[0],
  );

  protected readonly orders = signal<OrderResponse[]>([]);
  protected readonly total = signal(0);
  protected readonly statusFilter = signal<OrderStatusValue | null>(null);
  /**
   * What the selected customer can book right now: active, priced for their
   * customer type at their branch, and in stock. Anything else is left out,
   * and the server refuses it too.
   */
  protected readonly cylinderTypes = signal<OrderableCylinderTypeResponse[]>([]);
  protected readonly cylinderTypesLoading = signal(false);
  protected readonly cylinderTypeOptions = computed(() =>
    this.cylinderTypes().map((type) => ({
      value: type.cylinder_type_id,
      label: `${type.name} · ₹${type.unit_price} · ${type.available_quantity} in stock`,
    })),
  );

  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly statusOptions = [...STATUS_OPTIONS];
  protected readonly bookingSourceOptions = [...BOOKING_SOURCE_OPTIONS];

  protected readonly showCreateDrawer = signal(false);
  protected readonly createTrigger = viewChild<ElementRef<HTMLButtonElement>>('createTriggerEl');

  protected readonly selectedCustomer = signal<CustomerResponse | null>(null);
  protected readonly selectedAddress = signal<CustomerAddressResponse | null>(null);

  /** Validator-key → message for the create-booking fields. */
  protected readonly fieldMessages = {
    customer: { required: 'Select a customer.' },
    address_id: { required: 'Select a delivery address.' },
    requested_date: { required: 'Pick a requested delivery date.' },
  };

  protected readonly orderColumns: DataGridColumn<OrderResponse>[] = [
    {
      field: 'order_number',
      header: 'Order #',
      width: 130,
      valueFormatter: (value, row) => (value as string | null) ?? shortId(row.id),
      tooltipValueGetter: (_value, row) => row.order_number ?? row.id,
      onLinkClick: (row) => this.viewOrder(row),
    },
    {
      field: 'customer.full_name',
      header: 'Customer',
      flex: 2,
      valueFormatter: (_value, row) => row.customer?.full_name ?? '—',
      tooltipValueGetter: (_value, row) =>
        [row.customer?.full_name, row.customer?.consumer_number].filter(Boolean).join(' · '),
    },
    {
      field: 'customer.phone_number',
      header: 'Phone',
      valueFormatter: (_value, row) => row.customer?.phone_number ?? '—',
    },
    {
      field: 'customer.consumer_number',
      header: 'Consumer no.',
      valueFormatter: (_value, row) => row.customer?.consumer_number ?? '—',
    },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: STATUS_SEVERITY, labelMap: STATUS_LABELS },
    },
    {
      field: 'booking_source',
      header: 'Source',
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        labelMap: BOOKING_SOURCE_LABELS,
        severityMap: { mobile_app: 'info' },
      },
    },
    {
      field: 'requested_date',
      header: 'Delivery date',
      sortable: true,
      valueFormatter: (value) => formatReportDate(value),
    },
    {
      field: 'total_amount',
      header: 'Total',
      numeric: true,
      valueFormatter: (value) => (value ? formatCurrencyInr(value) : '—'),
    },
  ];

  protected readonly createForm = this.fb.group({
    customer: this.fb.control<CustomerResponse | null>(null, [Validators.required]),
    address_id: ['', [Validators.required]],
    booking_source: ['staff' as (typeof BOOKING_SOURCE_OPTIONS)[number]['value']],
    requested_date: [new Date(), [Validators.required]],
    lines: this.fb.array([this.buildLineGroup()]),
  });

  private buildLineGroup() {
    return this.fb.group({
      cylinder_type_id: ['', [Validators.required]],
      quantity: [1, [Validators.required, Validators.min(1)]],
    });
  }

  get lines() {
    return this.createForm.controls.lines;
  }

  ngOnInit(): void {
    this.loadOrders();
    this.route.queryParamMap.subscribe((params) => {
      if (params.get('create') === 'true') {
        this.openCreateDrawer();
      }
    });
  }

  protected loadOrders(opts: { silent?: boolean } = {}): void {
    if (!opts.silent) {
      this.loading.set(true);
    }
    const [from, to] = this.dateRange() ?? [];
    this.orderService
      .listOrders({
        status: this.statusFilter() ?? undefined,
        search: this.searchText(),
        fromDate: from ? startOfLocalDayIso(from) : undefined,
        toDate: from ? endOfLocalDayIso(to ?? from) : undefined,
        limit: 100,
      })
      .subscribe({
        next: (page) => {
          this.orders.set(page.items);
          this.total.set(page.total);
          this.loading.set(false);
        },
        error: (err) => {
          if (!opts.silent) {
            this.errorMessage.set(errorMessageFor(err));
          }
          this.loading.set(false);
        },
      });
  }

  private loadOrderableCylinderTypes(customer: CustomerResponse | null): void {
    this.cylinderTypes.set([]);
    while (this.lines.length > 1) this.lines.removeAt(0);
    this.lines.at(0)?.reset({ cylinder_type_id: '', quantity: 1 });
    if (!customer) return;

    this.cylinderTypesLoading.set(true);
    this.orderService.listOrderableCylinderTypes(customer.id).subscribe({
      next: (types) => {
        // A late answer for a customer no longer selected is dropped.
        if (this.selectedCustomer()?.id !== customer.id) return;
        this.cylinderTypes.set(types);
        this.cylinderTypesLoading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.cylinderTypesLoading.set(false);
      },
    });
  }

  /** Most of a cylinder type the branch can still promise, for the quantity input. */
  protected availableFor(cylinderTypeId: string): number | null {
    return (
      this.cylinderTypes().find((type) => type.cylinder_type_id === cylinderTypeId)
        ?.available_quantity ?? null
    );
  }

  protected onStatusFilterChange(value: OrderStatusValue | null): void {
    this.statusFilter.set(value);
    this.loadOrders();
  }

  protected onSearchChange(value: string): void {
    this.searchText.set(value);
    this.searchChanges.next();
  }

  protected onDateRangeChange(value: Date[] | null): void {
    this.dateRange.set(value);
    // A range is applied once both ends are picked (or cleared).
    if (!value || !value[0] || value[1]) this.loadOrders();
  }

  protected clearFilters(): void {
    this.statusFilter.set(null);
    this.searchText.set('');
    this.dateRange.set(null);
    this.loadOrders();
  }

  /** The primary address is chosen for the office so a booking is a few keys. */
  private preselectAddress(customer: CustomerResponse): void {
    const address =
      customer.addresses.find((a) => a.is_primary) ??
      (customer.addresses.length === 1 ? customer.addresses[0] : null);
    if (!address) return;
    this.createForm.controls.address_id.setValue(address.id);
    this.selectedAddress.set(address);
  }

  protected addressLabel(address: CustomerAddressResponse): string {
    return [address.line_1, address.line_2, address.area, address.city, address.pincode]
      .filter(Boolean)
      .join(', ');
  }

  protected viewOrder(order: OrderResponse): void {
    void this.router.navigate(['/orders', order.id]);
  }

  // ---------------------------------------------------------------------------
  // Create Order
  // ---------------------------------------------------------------------------

  protected openCreateDrawer(): void {
    this.selectedAddress.set(null);
    this.createForm.reset({
      customer: null,
      address_id: '',
      booking_source: 'staff',
      requested_date: new Date(),
    });
    while (this.lines.length > 1) this.lines.removeAt(0);
    this.lines.at(0)?.reset({ cylinder_type_id: '', quantity: 1 });
    this.showCreateDrawer.set(true);
  }

  protected closeCreateDrawer(): void {
    this.showCreateDrawer.set(false);
    void this.router.navigate([], { relativeTo: this.route, queryParams: {} });
  }

  protected onAddressChange(addressId: string): void {
    const address = this.selectedCustomer()?.addresses.find((a) => a.id === addressId) ?? null;
    this.selectedAddress.set(address);
  }

  protected addLine(): void {
    this.lines.push(this.buildLineGroup());
  }

  protected removeLine(index: number): void {
    if (this.lines.length > 1) this.lines.removeAt(index);
  }

  protected onSubmitCreate(): void {
    const customer = this.selectedCustomer();
    const address = this.selectedAddress();
    if (!customer || !address || this.createForm.invalid) {
      this.createForm.markAllAsTouched();
      return;
    }

    const val = this.createForm.getRawValue();
    this.loading.set(true);
    this.orderService
      .createOrder({
        branch_id: customer.branch_id,
        customer_id: customer.id,
        address_id: address.id,
        booking_source: val.booking_source,
        requested_date: deliveryDayIso(val.requested_date),
        lines: val.lines.map((line) => ({
          cylinder_type_id: line.cylinder_type_id,
          quantity: line.quantity,
        })),
      })
      .subscribe({
        next: (order) => {
          this.showCreateDrawer.set(false);
          this.loading.set(false);
          void this.router.navigate(['/orders', order.id]);
        },
        error: (err) => {
          this.errorMessage.set(errorMessageFor(err));
          this.loading.set(false);
        },
      });
  }
}
