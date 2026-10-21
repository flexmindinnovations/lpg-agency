import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  effect,
  inject,
  signal,
  viewChild,
  DestroyRef,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { AutoComplete } from 'primeng/autocomplete';
import type { AutoCompleteCompleteEvent } from 'primeng/types/autocomplete';
import { ButtonDirective } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Textarea } from 'primeng/textarea';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  AdminStaffUserService,
  CustomerService,
  NotifyService,
  OrderService,
  type CustomerResponse,
  type OrderResponse,
  type StaffUserResponse,
} from '@lpg/shared/data-access';
import {
  ComplaintService,
  type Complaint,
  type ComplaintAssignee,
  type ComplaintCategory,
  type ComplaintPriority,
  type ResolutionOutcome,
  type RaiseComplaintRequest,
  type AssignComplaintRequest,
  type ResolveComplaintRequest,
} from '../services/complaint.service';
import {
  DataGridComponent,
  type DataGridColumn,
  displayNameFromEmail,
  FormFieldComponent,
  HasPermissionDirective,
  PreviewDialog,
  type PreviewData,
  StatusChipCell,
  type ChipSeverity,
  shortId,
  toSentenceCase,
} from '@lpg/shared/ui';

/** Labels for the server's enum values (DO-19). */
const CATEGORY_LABELS: Record<ComplaintCategory, string> = {
  GasLeak: 'Gas leak / safety',
  ShortDelivery: 'Short delivery',
  DamagedCylinder: 'Damaged cylinder',
  BillingDispute: 'Billing dispute',
  DriverConduct: 'Driver conduct',
  LateDelivery: 'Late delivery',
  Other: 'Other',
};

/** A gas leak is always handled as Critical; the server enforces it too. */
const SAFETY_CATEGORIES = new Set<ComplaintCategory>(['GasLeak']);

const STATUS_LABELS: Record<string, string> = {
  Open: 'Open',
  Assigned: 'Assigned',
  InProgress: 'In progress',
  Resolved: 'Resolved',
  Rejected: 'Rejected',
  Closed: 'Closed',
};

/** Statuses after which nothing more can be done to a complaint (DO-20). */
const FINISHED_STATUSES = new Set(['Resolved', 'Rejected', 'Closed']);

function lowerKeys(record: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(record).map(([k, v]) => [k.toLowerCase(), v]));
}

@Component({
  selector: 'lib-feature-complaints',
  imports: [
    DatePipe,
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    Drawer,
    DrawerA11yDirective,
    AutoComplete,
    Select,
    Tag,
    Textarea,
    DataGridComponent,
    FormFieldComponent,
    HasPermissionDirective,
    PreviewDialog,
  ],
  templateUrl: './feature-complaints.html',
  styleUrl: './feature-complaints.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeatureComplaints implements OnInit {
  private readonly complaintService = inject(ComplaintService);
  private readonly customerService = inject(CustomerService);
  private readonly orderService = inject(OrderService);
  private readonly adminStaffUserService = inject(AdminStaffUserService);
  private readonly notify = inject(NotifyService);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly destroyRef = inject(DestroyRef);
  private readonly permissionChecker = inject(PERMISSION_CHECKER);

  readonly registerTriggerEl = viewChild<ElementRef<HTMLButtonElement>>('registerTriggerEl');

  protected readonly shortId = shortId;

  // State
  readonly complaints = signal<Complaint[]>([]);
  readonly loading = signal(true);

  /** Complaints only carry `customer_id` (a UUID, meaningless to a user) —
   * resolved to the real `CustomerResponse` (consumer number, name, etc.)
   * purely so the grid can display a real consumer number instead of a raw
   * UUID; unlike `feature-invoices` this backend doesn't denormalize a
   * `customer_consumer_number` onto the complaint itself, so there's
   * nothing to read off the row directly. */
  readonly customerById = signal<Map<string, CustomerResponse>>(new Map());

  // Customer/Staff "quick view" — both render through the shared
  // `PreviewDialog` (also used by `feature-invoices`) so there's one dialog
  // implementation instead of every feature re-inventing it.
  protected readonly customerPreviewDialog =
    viewChild.required<PreviewDialog>('customerPreviewDialog');
  protected readonly staffPreviewDialog = viewChild.required<PreviewDialog>('staffPreviewDialog');

  /** `AdminStaffUserService.listStaffUsers` requires `users:manage`, which
   * only `agency_admin`/`super_admin` hold — narrower than `complaints.manage`
   * (also granted to `manager`/`dispatcher`). Gate the Assigned To/Resolved By
   * links on that permission so those roles keep seeing the plain (unlinked)
   * ID they already saw rather than hitting a 403. */
  protected readonly canViewStaffDirectory = computed(
    () => this.permissionChecker()?.permissions?.has('users:manage') ?? false,
  );
  private readonly staffUsers = signal<StaffUserResponse[] | null>(null);

  /** id -> display name, so Assigned To/Resolved By can show "Admin" instead
   * of a raw UUID without waiting for the user to click through first. */
  protected readonly staffNameById = computed(() => {
    const map = new Map<string, string>();
    for (const user of this.staffUsers() ?? []) {
      map.set(user.id, displayNameFromEmail(user.email, toSentenceCase(user.role)));
    }
    return map;
  });

  private static readonly CUSTOMER_STATUS_SEVERITY: Record<string, ChipSeverity> = {
    onboarding: 'warn',
    pending_approval: 'warn',
    active: 'success',
    inactive: 'secondary',
    blocked: 'danger',
    closed: 'danger',
  };

  private static readonly KYC_STATUS_SEVERITY: Record<string, ChipSeverity> = {
    pending: 'warn',
    verified: 'success',
    rejected: 'danger',
    expired: 'danger',
  };

  protected readonly toSentenceCase = toSentenceCase;

  protected customerStatusSeverity(status: string): ChipSeverity {
    return FeatureComplaints.CUSTOMER_STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected kycStatusSeverity(status: string): ChipSeverity {
    return FeatureComplaints.KYC_STATUS_SEVERITY[status] ?? 'secondary';
  }

  // Drawer states
  readonly detailVisible = signal(false);
  readonly selectedComplaint = signal<Complaint | null>(null);
  /** The linked order's number for the detail drawer — a complaint only
   * carries the order's id. Null while loading, or when the viewer can't
   * read orders; the drawer falls back to a short id then. */
  protected readonly selectedOrderNumber = signal<string | null>(null);
  private readonly canReadOrders = computed(
    () => this.permissionChecker()?.permissions?.has('orders:read') ?? false,
  );

  readonly registerModalVisible = signal(false);
  readonly registerLoading = signal(false);

  readonly assignModalVisible = signal(false);
  readonly assignLoading = signal(false);

  readonly resolveModalVisible = signal(false);
  readonly resolveLoading = signal(false);

  // Grid config
  readonly columns: DataGridColumn<Complaint>[] = [
    {
      field: 'complaint_number',
      header: 'Complaint #',
      width: 140,
      tooltipValueGetter: (_val, row) => row.id,
      valueFormatter: (val, row) => (val as string | undefined) ?? shortId(row.id),
      // Without this the Assign/Resolve drawer (built around
      // `onRowAction`/`selectedComplaint`/`detailVisible` below) was
      // entirely unreachable — nothing in the grid ever called it.
      onLinkClick: (row) => this.onRowAction(row),
    },
    {
      field: 'category',
      header: 'Category',
      flex: 1,
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        labelMap: lowerKeys(CATEGORY_LABELS),
        severityMap: { gasleak: 'danger' },
      },
    },
    {
      field: 'priority',
      header: 'Priority',
      width: 150,
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        severityMap: { critical: 'danger', high: 'warn', medium: 'info', low: 'secondary' },
      },
    },
    {
      field: 'status',
      header: 'Status',
      width: 150,
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        // Real values are PascalCase with no separator ("InProgress") — the
        // lookup key is `raw.toLowerCase()`, hence "inprogress" below.
        labelMap: lowerKeys(STATUS_LABELS),
        severityMap: {
          open: 'warn',
          assigned: 'info',
          inprogress: 'info',
          resolved: 'success',
          rejected: 'danger',
          closed: 'secondary',
        },
      },
    },
    {
      field: 'customer_id',
      header: 'Customer',
      width: 190,
      tooltipValueGetter: (_val, row) =>
        [row.customer_phone, row.consumer_number].filter(Boolean).join(' · '),
      valueFormatter: (val, row) =>
        row.customer_name ?? this.customerById().get(String(val))?.full_name ?? shortId(val),
      onLinkClick: (row) => this.openCustomerPreview(row.customer_id),
    },
    {
      field: 'assignee_name',
      header: 'Assigned to',
      width: 170,
      valueFormatter: (val) => (val as string | null | undefined) ?? 'Not assigned',
    },
    {
      field: 'created_at',
      header: 'Raised On',
      width: 160,
      sortable: true,
      valueFormatter: (val) => new Date(String(val)).toLocaleDateString('en-GB'),
    },
  ];

  // Forms
  readonly raiseForm = this.fb.group({
    customer: [null as CustomerResponse | null, Validators.required],
    category: ['' as ComplaintCategory | '', Validators.required],
    priority: ['Medium' as ComplaintPriority, Validators.required],
    description: ['', [Validators.required, Validators.minLength(10)]],
    order_id: [''],
  });

  readonly assignForm = this.fb.group({
    assigned_to: ['', Validators.required],
  });

  readonly resolveForm = this.fb.group({
    outcome: ['Resolved', Validators.required],
    resolution_notes: ['', [Validators.required, Validators.minLength(5)]],
  });

  protected readonly fieldMessages = {
    customer: { required: 'Pick the customer by name, phone or consumer number.' },
    category: { required: 'Select a category.' },
    priority: { required: 'Select a priority.' },
    description: {
      required: 'A description is required.',
      minlength: 'Give a little more detail (at least 10 characters).',
    },
    assigned_to: { required: 'Pick who takes this complaint.' },
    outcome: { required: 'Select an outcome.' },
    resolution_notes: {
      required: 'Resolution notes are required.',
      minlength: 'Give a little more detail (at least 5 characters).',
    },
  };

  // Values must match the backend's `ComplaintCategory` enum exactly
  // (`domain/complaint/value_objects.py`) — these previously sent
  // human-readable labels as the raw value (e.g. `'Delivery Delay'`), none
  // of which matched the real enum, so raising a complaint with any
  // category but "Other" failed backend validation.
  readonly categoryOptions = (Object.keys(CATEGORY_LABELS) as ComplaintCategory[]).map((value) => ({
    label: CATEGORY_LABELS[value],
    value,
  }));

  protected categoryLabel(category: string): string {
    return CATEGORY_LABELS[category as ComplaintCategory] ?? category;
  }

  protected statusText(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }

  protected isFinished(complaint: Complaint): boolean {
    return FINISHED_STATUSES.has(complaint.status);
  }

  /** The picked customer's recent orders, for linking the complaint (DO-17). */
  protected readonly customerSuggestions = signal<CustomerResponse[]>([]);
  protected readonly customerOrders = signal<{ label: string; value: string }[]>([]);
  protected readonly assignees = signal<ComplaintAssignee[]>([]);
  protected readonly isSafetyCategory = signal(false);
  private latestCustomerQuery = '';

  protected searchCustomers(event: AutoCompleteCompleteEvent): void {
    const query = event.query?.replace(/\s+/g, ' ').trim() ?? '';
    this.latestCustomerQuery = query;
    if (query.length < 2) {
      this.customerSuggestions.set([]);
      return;
    }
    this.customerService.list(0, 20, query).subscribe({
      next: (page) => {
        if (query === this.latestCustomerQuery) this.customerSuggestions.set(page.items);
      },
      error: () => this.customerSuggestions.set([]),
    });
  }

  readonly priorityOptions = [
    { label: 'Critical', value: 'Critical' },
    { label: 'High', value: 'High' },
    { label: 'Medium', value: 'Medium' },
    { label: 'Low', value: 'Low' },
  ];

  readonly outcomeOptions = [
    { label: 'Resolved', value: 'Resolved' },
    { label: 'Compensated', value: 'Compensated' },
    { label: 'Rejected', value: 'Rejected' },
  ];

  constructor() {
    this.raiseForm.controls.customer.valueChanges.pipe(takeUntilDestroyed()).subscribe((value) => {
      this.raiseForm.controls.order_id.setValue('');
      this.customerOrders.set([]);
      const customer = value && typeof value === 'object' ? value : null;
      if (!customer || !this.canReadOrders()) return;
      this.orderService.listOrders({ customerId: customer.id, limit: 20 }).subscribe({
        next: (page) => this.customerOrders.set(page.items.map(orderOption)),
        error: () => this.customerOrders.set([]),
      });
    });
    this.raiseForm.controls.category.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((category) => {
        const safety = !!category && SAFETY_CATEGORIES.has(category);
        this.isSafetyCategory.set(safety);
        const priority = this.raiseForm.controls.priority;
        if (safety) {
          priority.setValue('Critical');
          priority.disable({ emitEvent: false });
        } else {
          priority.enable({ emitEvent: false });
        }
      });

    // Fetches the staff directory once permission is confirmed, so
    // Assigned To/Resolved By already show a name on first render instead
    // of only resolving after the user clicks through. Never attempted for
    // roles lacking `users:manage` — see `canViewStaffDirectory`.
    effect(() => {
      if (this.canViewStaffDirectory() && this.staffUsers() === null) {
        this.adminStaffUserService.listStaffUsers().subscribe({
          next: (users) => this.staffUsers.set(users),
          // Silent — Assigned To/Resolved By just keep showing the raw ID.
          error: () => undefined,
        });
      }
    });
  }

  ngOnInit() {
    this.loadComplaints();
  }

  loadComplaints() {
    this.loading.set(true);
    const sub = this.complaintService.listComplaints().subscribe({
      next: (res) => {
        // Names, phone and consumer number come with each complaint now.
        this.complaints.set(res.items);
        this.loading.set(false);
      },
      error: () => {
        this.notify.error('Failed to load complaints');
        this.loading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  onRowAction(complaint: Complaint) {
    this.selectedComplaint.set(complaint);
    this.detailVisible.set(true);
    this.loadOrderNumber(complaint.order_id);
  }

  private loadOrderNumber(orderId: string | null | undefined): void {
    this.selectedOrderNumber.set(null);
    if (!orderId || !this.canReadOrders()) return;
    const sub = this.orderService
      .getOrder(orderId)
      .pipe(
        map((order) => order.order_number ?? null),
        catchError(() => of(null)),
      )
      .subscribe((orderNumber) => {
        if (this.selectedComplaint()?.order_id === orderId) {
          this.selectedOrderNumber.set(orderNumber);
        }
      });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  /** Same shape as `feature-invoices`'s `openCustomerPreview` — a fresh
   * fetch on every open rather than reading `customerById`, since that
   * map exists only to feed the grid's `valueFormatter` and isn't meant
   * to double as a cache the preview depends on staying in sync with. */
  protected openCustomerPreview(customerId: string): void {
    const dialog = this.customerPreviewDialog();
    dialog.open();
    this.customerService.get(customerId).subscribe({
      next: (customer) => {
        const address = this.customerPreviewAddress(customer);
        dialog.showData({
          title: customer.full_name,
          subtitle: `Consumer No: ${customer.consumer_number ?? '—'}`,
          tags: [
            {
              label: toSentenceCase(customer.status),
              severity: this.customerStatusSeverity(customer.status),
            },
            {
              label: 'KYC: ' + toSentenceCase(customer.kyc_status),
              severity: this.kycStatusSeverity(customer.kyc_status),
            },
          ],
          fields: [
            { label: 'Phone', value: customer.phone_number },
            { label: 'Customer Type', value: toSentenceCase(customer.customer_type) },
          ],
          fullWidthFields: address ? [{ label: 'Address', value: address }] : [],
        });
      },
      error: () => {
        dialog.close();
        this.notify.error('That customer could not be found.');
      },
    });
  }

  protected customerPreviewAddress(customer: CustomerResponse): string | null {
    const address = customer.addresses.find((a) => a.is_primary) ?? customer.addresses[0];
    if (!address) return null;
    return [
      address.line_1,
      address.line_2,
      address.area,
      address.city,
      address.state,
      address.pincode,
    ]
      .filter(Boolean)
      .join(', ');
  }

  /** `assigned_to`/`resolved_by` are `identity_user.id` values — the only
   * client-visible endpoint that maps that id space to a name is the admin
   * staff directory (`AdminStaffUserService.listStaffUsers`, no get-by-id
   * exists), so the whole list is fetched once and cached rather than
   * re-fetched per click. Only reachable when `canViewStaffDirectory()` is
   * true — see that computed's comment for why. */
  protected openStaffPreview(userId: string): void {
    const dialog = this.staffPreviewDialog();
    dialog.open();
    const cached = this.staffUsers();
    if (cached) {
      this.showStaffPreview(dialog, cached, userId);
      return;
    }
    this.adminStaffUserService.listStaffUsers().subscribe({
      next: (users) => {
        this.staffUsers.set(users);
        this.showStaffPreview(dialog, users, userId);
      },
      error: () => {
        dialog.close();
        this.notify.error('Could not load the staff directory.');
      },
    });
  }

  private showStaffPreview(
    dialog: PreviewDialog,
    users: StaffUserResponse[],
    userId: string,
  ): void {
    const user = users.find((u) => u.id === userId);
    if (!user) {
      dialog.close();
      this.notify.error('That staff member could not be found.');
      return;
    }
    const data: PreviewData = {
      title: this.staffNameById().get(user.id) ?? shortId(user.id),
      subtitle: user.email ?? undefined,
      tags: [
        {
          label: user.is_active ? 'Active' : 'Inactive',
          severity: user.is_active ? 'success' : 'secondary',
        },
      ],
      fields: [{ label: 'Role', value: toSentenceCase(user.role) }],
    };
    dialog.showData(data);
  }

  openRaiseModal() {
    this.raiseForm.reset({ priority: 'Medium' });
    this.customerOrders.set([]);
    this.registerModalVisible.set(true);
  }

  closeRaiseModal() {
    this.registerModalVisible.set(false);
    this.registerTriggerEl()?.nativeElement.focus();
  }

  submitRaise() {
    const val = this.raiseForm.getRawValue();
    const customer = val.customer && typeof val.customer === 'object' ? val.customer : null;
    if (this.raiseForm.invalid || !customer || !val.category) {
      this.raiseForm.markAllAsTouched();
      return;
    }
    this.registerLoading.set(true);

    const request: RaiseComplaintRequest = {
      customer_id: customer.id,
      category: val.category,
      priority: val.priority,
      description: val.description.trim(),
      order_id: val.order_id || null,
    };

    const sub = this.complaintService.raiseComplaint(request).subscribe({
      next: () => {
        this.notify.success('Complaint raised');
        this.closeRaiseModal();
        this.loadComplaints();
        this.registerLoading.set(false);
      },
      error: () => {
        // The app-wide error toast already explains the failure.
        this.registerLoading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  openAssignModal() {
    this.assignForm.reset({
      assigned_to: this.selectedComplaint()?.assignments?.at(-1)?.assigned_to ?? '',
    });
    if (this.assignees().length === 0) {
      this.complaintService.listAssignees().subscribe({
        next: (staff) => this.assignees.set(staff),
        error: () => this.assignees.set([]),
      });
    }
    this.assignModalVisible.set(true);
  }

  closeAssignModal() {
    this.assignModalVisible.set(false);
  }

  submitAssign() {
    const complaint = this.selectedComplaint();
    if (this.assignForm.invalid || !complaint) return;

    this.assignLoading.set(true);
    const request: AssignComplaintRequest = {
      assigned_to: this.assignForm.getRawValue().assigned_to,
    };

    const sub = this.complaintService.assignComplaint(complaint.id, request).subscribe({
      next: () => {
        this.notify.success('Complaint assigned');
        this.closeAssignModal();
        this.loadComplaints();
        // Refresh detail
        this.refreshDetail(complaint.id);
        this.assignLoading.set(false);
      },
      error: () => {
        // The app-wide error toast already explains the failure.
        this.assignLoading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  openResolveModal() {
    this.resolveForm.reset({ outcome: 'Resolved' });
    this.resolveModalVisible.set(true);
  }

  closeResolveModal() {
    this.resolveModalVisible.set(false);
  }

  submitResolve() {
    const complaint = this.selectedComplaint();
    if (this.resolveForm.invalid || !complaint) return;

    this.resolveLoading.set(true);
    const val = this.resolveForm.getRawValue();
    const request: ResolveComplaintRequest = {
      outcome: val.outcome as ResolutionOutcome,
      resolution_notes: val.resolution_notes.trim(),
    };

    const sub = this.complaintService.resolveComplaint(complaint.id, request).subscribe({
      next: () => {
        this.notify.success('Complaint resolved');
        this.closeResolveModal();
        this.loadComplaints();
        // Refresh detail
        this.refreshDetail(complaint.id);
        this.resolveLoading.set(false);
      },
      error: () => {
        // The app-wide error toast already explains the failure.
        this.resolveLoading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  private refreshDetail(id: string) {
    const sub = this.complaintService.getComplaint(id).subscribe({
      next: (comp) => {
        this.selectedComplaint.set(comp);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  getSeverity(status: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' {
    switch (status) {
      case 'Resolved':
        return 'success';
      case 'Open':
        return 'warn';
      case 'InProgress':
        return 'info';
      case 'Closed':
        return 'secondary';
      case 'Rejected':
        return 'danger';
      default:
        return 'info';
    }
  }
}

function orderOption(order: OrderResponse): { label: string; value: string } {
  const day = new Date(order.requested_date).toLocaleDateString('en-GB');
  return { label: `${order.order_number ?? shortId(order.id)} · ${day}`, value: order.id };
}
