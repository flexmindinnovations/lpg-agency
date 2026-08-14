import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, ElementRef, OnInit, inject, signal, viewChild } from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Button, ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { DatePicker } from 'primeng/datepicker';
import { Drawer } from 'primeng/drawer';
import { InputNumber } from 'primeng/inputnumber';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import {
  AdminCylinderTypeService,
  OrderService,
  type CustomerAddressResponse,
  type CustomerResponse,
  type CylinderTypeResponse,
  type OrderResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';
import { CustomerAutocomplete } from '../customer-autocomplete/customer-autocomplete';
import { errorMessageFor, statusLabel } from '../order-status.util';

const STATUS_OPTIONS = [
  { label: 'Draft', value: 'draft' },
  { label: 'Booked', value: 'booked' },
  { label: 'Confirmed', value: 'confirmed' },
  { label: 'Assigned', value: 'assigned' },
  { label: 'Ready for Dispatch', value: 'ready_for_dispatch' },
  { label: 'Out for Delivery', value: 'out_for_delivery' },
  { label: 'Delivered', value: 'delivered' },
  { label: 'Failed Delivery', value: 'failed_delivery' },
  { label: 'Cancelled', value: 'cancelled' },
  { label: 'Closed', value: 'closed' },
] as const;

const BOOKING_SOURCE_OPTIONS = [
  { label: 'Staff', value: 'staff' },
  { label: 'Phone', value: 'phone' },
  { label: 'Walk-in', value: 'walk_in' },
  { label: 'Mobile App', value: 'mobile_app' },
  { label: 'WhatsApp', value: 'whatsapp' },
  { label: 'API', value: 'api' },
] as const;

@Component({
  selector: 'lpg-order-queue',
  standalone: true,
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, 
    FormsModule,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    Button,
    Drawer,
    Message,
    Select,
    InputNumber,
    DatePicker,
    DataGridComponent,
    CustomerAutocomplete,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './order-queue.html',
  styleUrl: './order-queue.css',
})
export class OrderQueue implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly orderService = inject(OrderService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly orders = signal<OrderResponse[]>([]);
  protected readonly total = signal(0);
  protected readonly statusFilter = signal<string | null>(null);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);

  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly statusOptions = [...STATUS_OPTIONS];
  protected readonly bookingSourceOptions = [...BOOKING_SOURCE_OPTIONS];

  protected readonly showCreateDrawer = signal(false);
  protected readonly createTrigger = viewChild<ElementRef<HTMLButtonElement>>('createTriggerEl');

  protected readonly selectedCustomer = signal<CustomerResponse | null>(null);
  protected readonly selectedAddress = signal<CustomerAddressResponse | null>(null);

  protected readonly orderColumns: DataGridColumn<OrderResponse>[] = [
    {
      field: 'id',
      header: 'Order ID',
      valueFormatter: (value) => `${(value as string).split('-')[0]}…`,
      tooltipValueGetter: (value) => value as string,
      onLinkClick: (row) => this.viewOrder(row),
    },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      valueFormatter: (value) => statusLabel(value as string),
    },
    { field: 'booking_source', header: 'Source', valueFormatter: (value) => statusLabel(value as string) },
    {
      field: 'requested_date',
      header: 'Requested',
      sortable: true,
      valueFormatter: (value) => new Date(value as string).toLocaleString(),
    },
    {
      field: 'total_amount',
      header: 'Total',
      numeric: true,
      valueFormatter: (value) => (value ? `₹${value}` : '—'),
    },
  ];

  protected readonly createForm = this.fb.group({
    address_id: ['', [Validators.required]],
    booking_source: ['staff' as (typeof BOOKING_SOURCE_OPTIONS)[number]['value'], [Validators.required]],
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
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (ct) => this.cylinderTypes.set(ct),
    });
    this.route.queryParamMap.subscribe((params) => {
      if (params.get('create') === 'true') {
        this.openCreateDrawer();
      }
    });
  }

  protected loadOrders(): void {
    this.loading.set(true);
    this.orderService.listOrders({ status: this.statusFilter() ?? undefined, limit: 100 }).subscribe({
      next: (page) => {
        this.orders.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(errorMessageFor(err));
        this.loading.set(false);
      },
    });
  }

  protected onStatusFilterChange(value: string | null): void {
    this.statusFilter.set(value);
    this.loadOrders();
  }

  protected viewOrder(order: OrderResponse): void {
    void this.router.navigate(['/orders', order.id]);
  }

  // ---------------------------------------------------------------------------
  // Create Order
  // ---------------------------------------------------------------------------

  protected openCreateDrawer(): void {
    this.selectedCustomer.set(null);
    this.selectedAddress.set(null);
    this.createForm.reset({
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

  protected onCustomerSelected(customer: CustomerResponse | null): void {
    this.selectedCustomer.set(customer);
    this.selectedAddress.set(null);
    this.createForm.patchValue({ address_id: '' });
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
    if (!customer || !address || this.createForm.invalid) return;

    const val = this.createForm.getRawValue();
    this.loading.set(true);
    this.orderService
      .createOrder({
        branch_id: customer.branch_id,
        customer_id: customer.id,
        address_id: val.address_id,
        delivery_address: {
          address_line: address.address_line,
          latitude: address.latitude ? Number(address.latitude) : null,
          longitude: address.longitude ? Number(address.longitude) : null,
        },
        booking_source: val.booking_source,
        requested_date: val.requested_date.toISOString(),
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
