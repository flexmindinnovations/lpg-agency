import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
  DestroyRef,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable, forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Textarea } from 'primeng/textarea';
import { MessageService } from 'primeng/api';
import { PERMISSION_CHECKER } from '@lpg/shared/util';
import { HeaderPortalDirective, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  AdminStaffUserService,
  CustomerService,
  type CustomerResponse,
  type StaffUserResponse,
} from '@lpg/shared/data-access';
import {
  ComplaintService,
  type Complaint,
  type RaiseComplaintRequest,
  type AssignComplaintRequest,
  type ResolveComplaintRequest,
} from '../services/complaint.service';
import {
  DataGridComponent,
  type DataGridColumn,
  HasPermissionDirective,
  PreviewDialog,
  type PreviewData,
  StatusChipCell,
  type ChipSeverity,
  shortId,
  toSentenceCase,
} from '@lpg/shared/ui';

function errorMessageFor(_error: unknown): string {
  // Add specific error handling if backend returns AppError structures
  return 'Something went wrong. Please try again.';
}

@Component({
  selector: 'lib-feature-complaints',
  imports: [
    DatePipe,
    HeaderPortalDirective,
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    Drawer,
    InputText,
    Select,
    Tag,
    Textarea,
    DataGridComponent,
    HasPermissionDirective,
    PreviewDialog,
  ],
  templateUrl: './feature-complaints.html',
  styleUrl: './feature-complaints.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [MessageService],
})
export class FeatureComplaints implements OnInit {
  private readonly complaintService = inject(ComplaintService);
  private readonly customerService = inject(CustomerService);
  private readonly adminStaffUserService = inject(AdminStaffUserService);
  private readonly messageService = inject(MessageService);
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
  protected readonly customerPreviewDialog = viewChild.required<PreviewDialog>('customerPreviewDialog');
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
    { field: 'category', header: 'Category', flex: 1, sortable: true, cellRenderer: StatusChipCell },
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
      tooltipValueGetter: (val) => String(val),
      valueFormatter: (val) =>
        this.customerById().get(String(val))?.full_name ?? shortId(val),
      onLinkClick: (row) => this.openCustomerPreview(row.customer_id),
    },
    {
      field: 'created_at',
      header: 'Raised On',
      width: 160,
      sortable: true,
      valueFormatter: (val) => new Date(String(val)).toLocaleDateString(),
    },
  ];

  // Forms
  readonly raiseForm = this.fb.group({
    customer_id: ['', Validators.required],
    category: ['', Validators.required],
    priority: ['Medium', Validators.required],
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

  // Values must match the backend's `ComplaintCategory` enum exactly
  // (`domain/complaint/value_objects.py`) — these previously sent
  // human-readable labels as the raw value (e.g. `'Delivery Delay'`), none
  // of which matched the real enum, so raising a complaint with any
  // category but "Other" failed backend validation.
  readonly categoryOptions = [
    { label: 'Short Delivery', value: 'ShortDelivery' },
    { label: 'Damaged Cylinder', value: 'DamagedCylinder' },
    { label: 'Billing Dispute', value: 'BillingDispute' },
    { label: 'Driver Conduct', value: 'DriverConduct' },
    { label: 'Late Delivery', value: 'LateDelivery' },
    { label: 'Other', value: 'Other' },
  ];

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

  ngOnInit() {
    this.loadComplaints();
  }

  loadComplaints() {
    this.loading.set(true);
    const sub = this.complaintService.listComplaints().subscribe({
      next: (res) => {
        // Resolve every complaint's customer before the grid first renders
        // rather than after — a `valueFormatter` re-run on signal change
        // isn't guaranteed the moment `customerById` fills in later, so
        // fetching first avoids ever showing the raw UUID and then
        // replacing it.
        this.resolveCustomers(res.items.map((c) => c.customer_id)).subscribe(() => {
          this.complaints.set(res.items);
          this.loading.set(false);
        });
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to load complaints',
        });
        this.loading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  /** Fetches any customer IDs not already cached in `customerById` and
   * merges them in. Never errors the caller — a customer lookup failing
   * (deleted customer, transient error) falls back to the raw ID via
   * `shortId` rather than blocking the complaints list from loading. */
  private resolveCustomers(customerIds: string[]): Observable<void> {
    const known = this.customerById();
    const missing = [...new Set(customerIds)].filter((id) => !known.has(id));
    if (missing.length === 0) return of(undefined);

    return forkJoin(
      missing.map((id) => this.customerService.get(id).pipe(catchError(() => of(null)))),
    ).pipe(
      map((results) => {
        const next = new Map(this.customerById());
        for (const customer of results) {
          if (customer) next.set(customer.id, customer);
        }
        this.customerById.set(next);
      }),
    );
  }

  onRowAction(complaint: Complaint) {
    this.selectedComplaint.set(complaint);
    this.detailVisible.set(true);
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
            { label: toSentenceCase(customer.status), severity: this.customerStatusSeverity(customer.status) },
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
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'That customer could not be found.',
        });
      },
    });
  }

  protected customerPreviewAddress(customer: CustomerResponse): string | null {
    const address = customer.addresses.find((a) => a.is_primary) ?? customer.addresses[0];
    if (!address) return null;
    return [address.line_1, address.line_2, address.area, address.city, address.state, address.pincode]
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
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Could not load the staff directory.',
        });
      },
    });
  }

  private showStaffPreview(dialog: PreviewDialog, users: StaffUserResponse[], userId: string): void {
    const user = users.find((u) => u.id === userId);
    if (!user) {
      dialog.close();
      this.messageService.add({
        severity: 'error',
        summary: 'Error',
        detail: 'That staff member could not be found.',
      });
      return;
    }
    const data: PreviewData = {
      title: user.email ?? shortId(user.id),
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
    this.registerModalVisible.set(true);
  }

  closeRaiseModal() {
    this.registerModalVisible.set(false);
    this.registerTriggerEl()?.nativeElement.focus();
  }

  submitRaise() {
    if (this.raiseForm.invalid) return;
    this.registerLoading.set(true);
    const val = this.raiseForm.getRawValue();

    const request: RaiseComplaintRequest = {
      customer_id: val.customer_id,
      category: val.category,
      priority: val.priority,
      description: val.description,
      order_id: val.order_id || undefined,
    };

    const sub = this.complaintService.raiseComplaint(request).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Complaint raised',
        });
        this.closeRaiseModal();
        this.loadComplaints();
        this.registerLoading.set(false);
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: errorMessageFor(_err),
        });
        this.registerLoading.set(false);
      },
    });
    this.destroyRef.onDestroy(() => sub.unsubscribe());
  }

  openAssignModal() {
    this.assignForm.reset();
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
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Complaint assigned',
        });
        this.closeAssignModal();
        this.loadComplaints();
        // Refresh detail
        this.refreshDetail(complaint.id);
        this.assignLoading.set(false);
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: errorMessageFor(_err),
        });
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
      outcome: val.outcome as 'Resolved' | 'Compensated' | 'Rejected',
      resolution_notes: val.resolution_notes,
    };

    const sub = this.complaintService.resolveComplaint(complaint.id, request).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Complaint resolved',
        });
        this.closeResolveModal();
        this.loadComplaints();
        // Refresh detail
        this.refreshDetail(complaint.id);
        this.resolveLoading.set(false);
      },
      error: (_err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: errorMessageFor(_err),
        });
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
