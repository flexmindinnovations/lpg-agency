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
import { CurrencyPipe } from '@angular/common';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subject, debounceTime } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DomSanitizer, type SafeResourceUrl } from '@angular/platform-browser';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { IconField } from 'primeng/iconfield';
import { Tag } from 'primeng/tag';
import { Drawer } from 'primeng/drawer';
import {
  DateRangeFilterComponent,
  DrawerA11yDirective,
  ExportButtonComponent,
  type DateRangeValue,
} from '@lpg/shared/ui';
import { Dialog } from 'primeng/dialog';
import { ButtonDirective } from 'primeng/button';
import { Select } from 'primeng/select';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Message } from 'primeng/message';
import { MessageService } from 'primeng/api';
import {
  DataGridComponent,
  type DataGridColumn,
  PreviewDialog,
  type PreviewData,
  StatusChipCell,
  type ChipSeverity,
  bookingSourceLabel,
  toSentenceCase,
  formatCurrencyInr,
  FormFieldComponent,
} from '@lpg/shared/ui';
import {
  LpgDatePipe,
  LpgDateTimePipe,
  PERMISSION_CHECKER,
  formatDisplayDate,
} from '@lpg/shared/util';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  AdminCylinderTypeService,
  CustomerService,
  InvoiceService,
  OrderService,
  PrintingService,
  errorMessageFor,
  type CreditNoteResponse,
  type CustomerResponse,
  type CylinderTypeResponse,
  type InvoiceResponse,
  type OrderResponse,
  type StaffPaymentMethod,
  type UninvoicedOrderResponse,
} from '@lpg/shared/data-access';

/** Methods that must carry a reference the accountant can match against
 * the bank statement — mirrors the backend rule. */
const REFERENCE_REQUIRED: ReadonlySet<StaffPaymentMethod> = new Set(['cheque', 'bank_transfer']);

@Component({
  selector: 'lpg-feature-invoices',
  standalone: true,
  imports: [
    DrawerA11yDirective,
    HeaderTitlePortalDirective,
    Drawer,
    Dialog,
    InputIcon,
    InputText,
    IconField,
    Tag,
    ButtonDirective,
    DataGridComponent,
    PreviewDialog,
    LpgDatePipe,
    LpgDateTimePipe,
    CurrencyPipe,
    FormsModule,
    ReactiveFormsModule,
    Select,
    RouterLink,
    DateRangeFilterComponent,
    ExportButtonComponent,
    Message,
    FormFieldComponent,
  ],
  templateUrl: './feature-invoices.html',
  styleUrl: './feature-invoices.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeatureInvoices implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly invoiceService = inject(InvoiceService);
  private readonly printingService = inject(PrintingService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly customerService = inject(CustomerService);
  private readonly permissions = inject(PERMISSION_CHECKER);
  private readonly fb = inject(FormBuilder);
  private readonly orderService = inject(OrderService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly messageService = inject(MessageService);

  readonly isLoading = signal(false);
  readonly loadError = signal<string | null>(null);
  readonly isPrinting = signal(false);
  readonly invoices = signal<InvoiceResponse[]>([]);
  readonly selectedInvoice = signal<InvoiceResponse | null>(null);
  readonly searchQuery = signal('');
  private readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);

  // Server-side paging and filters (DA-07) — the list is no longer capped
  // at the first 100 invoices.
  protected readonly page = signal(1);
  protected readonly pageSize = signal(25);
  protected readonly total = signal(0);
  protected readonly statusFilter = signal<string | null>(null);
  protected readonly issuedFrom = signal('');
  protected readonly issuedTo = signal('');
  private readonly searchChanges = new Subject<string>();

  protected readonly statusOptions = [
    { label: 'Issued', value: 'issued' },
    { label: 'Partially paid', value: 'partially_paid' },
    { label: 'Paid', value: 'paid' },
    { label: 'Refunded', value: 'refunded' },
    { label: 'Cancelled', value: 'cancelled' },
  ];

  // Invoices on hold (DA-06): delivered orders not invoiced because GST was
  // not configured, issued from here once it is.
  protected readonly heldOrders = signal<UninvoicedOrderResponse[]>([]);
  protected readonly issuingOrderId = signal<string | null>(null);
  protected readonly heldDialogVisible = signal(false);

  // Payments, refunds and payment links (DA-07).
  protected readonly creditNotes = signal<CreditNoteResponse[]>([]);
  protected readonly paymentDrawerVisible = signal(false);
  protected readonly refundDrawerVisible = signal(false);
  protected readonly submitting = signal(false);
  protected readonly paymentLinkUrl = signal<string | null>(null);
  protected readonly paymentLinkError = signal<string | null>(null);
  protected readonly paymentMethodOptions: { label: string; value: StaffPaymentMethod }[] = [
    { label: 'Cash', value: 'cash' },
    { label: 'UPI', value: 'upi' },
    { label: 'Card', value: 'card' },
    { label: 'Cheque', value: 'cheque' },
    { label: 'Bank transfer (NEFT/RTGS/IMPS)', value: 'bank_transfer' },
  ];
  readonly paymentForm = this.fb.nonNullable.group({
    method: this.fb.nonNullable.control<StaffPaymentMethod>('cash', Validators.required),
    amount: ['', [Validators.required, Validators.pattern(/^\d+(\.\d{1,2})?$/)]],
    reference: ['', Validators.maxLength(100)],
  });
  protected readonly refundForm = this.fb.nonNullable.group({
    amount: ['', [Validators.required, Validators.pattern(/^\d+(\.\d{1,2})?$/)]],
    reason: ['', [Validators.required, Validators.maxLength(500)]],
  });
  protected readonly referenceRequired = signal(false);

  protected readonly canIssue = computed(() => this.can('invoices:issue'));
  protected readonly canRecordPayment = computed(() => this.can('invoices:record_payment'));
  protected readonly canApproveRefund = computed(() => this.can('credit_notes:approve'));

  protected readonly cylinderTypeNameById = computed(() => {
    const map = new Map<string, string>();
    for (const ct of this.cylinderTypes()) map.set(ct.id, ct.name);
    return map;
  });

  // Thermal receipt preview — embedded via iframe so printing/inspecting a
  // receipt never navigates the user away from the invoice they had open.
  protected readonly showThermalDialog = signal(false);
  protected readonly thermalReceiptUrl = signal<string | null>(null);
  protected readonly thermalReceiptSafeUrl = computed<SafeResourceUrl | null>(() => {
    const url = this.thermalReceiptUrl();
    return url ? this.sanitizer.bypassSecurityTrustResourceUrl(url) : null;
  });
  private readonly thermalFrame = viewChild<ElementRef<HTMLIFrameElement>>('thermalFrame');

  // Customer/Order "quick view" — a lightweight read-only preview so
  // clicking a reference number from the invoice drawer doesn't navigate
  // away and lose the invoice context (matches the drawer-not-full-page
  // pattern used everywhere else in this app). Customer preview renders
  // through the shared `PreviewDialog` (also used by `feature-complaints`);
  // Order preview keeps its own dialog since it has richer content (a line
  // item list) that doesn't fit the shared component's simple field-grid shape.
  protected readonly customerPreviewDialog =
    viewChild.required<PreviewDialog>('customerPreviewDialog');

  protected readonly showOrderPreview = signal(false);
  protected readonly orderPreview = signal<OrderResponse | null>(null);
  protected readonly orderPreviewLoading = signal(false);

  private static readonly STATUS_SEVERITY: Record<string, ChipSeverity> = {
    draft: 'secondary',
    issued: 'info',
    partially_paid: 'warn',
    paid: 'success',
    cancelled: 'danger',
    refunded: 'danger',
  };

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

  private static readonly ORDER_STATUS_SEVERITY: Record<string, ChipSeverity> = {
    draft: 'secondary',
    booked: 'info',
    confirmed: 'info',
    assigned: 'warn',
    ready_for_dispatch: 'warn',
    out_for_delivery: 'warn',
    delivered: 'success',
    failed_delivery: 'danger',
    cancelled: 'danger',
    closed: 'success',
  };

  protected readonly toSentenceCase = toSentenceCase;
  protected readonly bookingSourceLabel = bookingSourceLabel;

  protected statusSeverity(status: string): ChipSeverity {
    return FeatureInvoices.STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected customerStatusSeverity(status: string): ChipSeverity {
    return FeatureInvoices.CUSTOMER_STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected kycStatusSeverity(status: string): ChipSeverity {
    return FeatureInvoices.KYC_STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected orderStatusSeverity(status: string): ChipSeverity {
    return FeatureInvoices.ORDER_STATUS_SEVERITY[status] ?? 'secondary';
  }

  readonly columns: DataGridColumn<InvoiceResponse>[] = [
    {
      field: 'invoice_number',
      header: 'Invoice #',
      sortable: true,
      onLinkClick: (row) => this.onInvoiceSelected(row),
      valueFormatter: (val) => (val as string | null) ?? 'Not numbered',
    },
    {
      field: 'issued_at',
      header: 'Date',
      sortable: true,
      valueFormatter: (val) => formatDisplayDate(val),
    },
    {
      field: 'customer_name',
      header: 'Customer',
      sortable: true,
      valueFormatter: (val, row) =>
        (val as string | null) ?? row.customer_consumer_number ?? 'Unknown customer',
    },
    {
      field: 'order_number',
      header: 'Order #',
      sortable: true,
      valueFormatter: (val) => (val as string | null) ?? '—',
    },
    {
      field: 'total_amount',
      header: 'Total',
      sortable: true,
      numeric: true,
      valueFormatter: (val) => formatCurrencyInr(val),
    },
    {
      field: 'balance_due',
      header: 'Balance due',
      sortable: true,
      numeric: true,
      valueFormatter: (val) => formatCurrencyInr(val ?? 0),
    },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        severityMap: FeatureInvoices.STATUS_SEVERITY,
      },
    },
  ];

  protected readonly paymentMethodLabel = (method: string): string =>
    this.paymentMethodOptions.find((o) => o.value === method)?.label ??
    (method === 'online_gateway' ? 'Online (Razorpay)' : toSentenceCase(method));

  protected readonly placeOfSupply = (inv: InvoiceResponse): string =>
    inv.place_of_supply_state_code ?? '—';

  constructor() {
    this.searchChanges.pipe(debounceTime(300), takeUntilDestroyed()).subscribe((query) => {
      this.searchQuery.set(query);
      this.page.set(1);
      this.loadInvoices();
    });
    this.paymentForm.controls.method.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((method) => this.applyReferenceRule(method));
  }

  ngOnInit(): void {
    this.openLinkedInvoice();
    this.loadInvoices();
    this.loadHeldOrders();
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (types) => this.cylinderTypes.set(types),
    });
  }

  /** `/invoices?invoice=<id>` (from an order page) opens that invoice. */
  private openLinkedInvoice(): void {
    const id = this.route.snapshot.queryParamMap.get('invoice');
    if (!id) return;
    this.invoiceService.get(id).subscribe({
      next: (invoice) => this.onInvoiceSelected(invoice),
    });
  }

  protected readonly isSending = signal(false);

  sendToCustomer(): void {
    const inv = this.selectedInvoice();
    if (!inv) return;
    this.isSending.set(true);
    this.invoiceService.sendToCustomer(inv.invoice_id).subscribe({
      next: () => {
        this.isSending.set(false);
        this.messageService.add({
          severity: 'success',
          summary: 'Invoice sent',
          detail: `${inv.invoice_number ?? 'The invoice'} was sent to ${inv.customer_name ?? 'the customer'}.`,
        });
      },
      error: () => this.isSending.set(false),
    });
  }

  loadInvoices(): void {
    this.isLoading.set(true);
    this.loadError.set(null);
    this.invoiceService
      .list({
        page: this.page(),
        pageSize: this.pageSize(),
        status: this.statusFilter(),
        issuedFrom: this.issuedFrom(),
        issuedTo: this.issuedTo(),
        search: this.searchQuery(),
      })
      .subscribe({
        next: (res) => {
          this.invoices.set(res.items);
          this.total.set(res.total);
          this.isLoading.set(false);
        },
        error: (error: unknown) => {
          this.loadError.set(errorMessageFor(error));
          this.isLoading.set(false);
        },
      });
  }

  protected onSearch(query: string): void {
    this.searchChanges.next(query);
  }

  protected onStatusChange(status: string | null): void {
    this.statusFilter.set(status);
    this.page.set(1);
    this.loadInvoices();
  }

  protected onDateRangeChange(range: DateRangeValue): void {
    this.issuedFrom.set(range.from ?? '');
    this.issuedTo.set(range.to ?? '');
    this.page.set(1);
    this.loadInvoices();
  }

  protected clearFilters(): void {
    this.statusFilter.set(null);
    this.issuedFrom.set('');
    this.issuedTo.set('');
    this.searchQuery.set('');
    this.page.set(1);
    this.loadInvoices();
  }

  protected onPageChange(event: { page: number; pageSize: number }): void {
    this.pageSize.set(event.pageSize);
    this.page.set(event.page);
    this.loadInvoices();
  }

  protected exportCsv(): void {
    this.grid()?.exportCsv(`invoices-page-${this.page()}`);
  }

  private readonly grid = viewChild(DataGridComponent);

  protected loadHeldOrders(): void {
    if (!this.can('invoices:issue')) return;
    this.invoiceService.listUninvoicedOrders().subscribe({
      next: (orders) => this.heldOrders.set(orders),
      error: () => this.heldOrders.set([]),
    });
  }

  protected issueHeldInvoice(order: UninvoicedOrderResponse): void {
    this.issuingOrderId.set(order.order_id);
    // A GST_NOT_CONFIGURED refusal is toasted by the global error
    // interceptor with the backend's own instructions.
    this.invoiceService.issueForOrder(order.order_id).subscribe({
      next: (invoice) => {
        this.issuingOrderId.set(null);
        this.messageService.add({
          severity: 'success',
          summary: 'Invoice issued',
          detail: `${invoice.invoice_number ?? 'Invoice'} issued for ${order.order_number ?? 'the order'}.`,
        });
        this.loadHeldOrders();
        this.loadInvoices();
      },
      error: () => this.issuingOrderId.set(null),
    });
  }

  onInvoiceSelected(invoice: InvoiceResponse): void {
    this.selectedInvoice.set(invoice);
    this.paymentLinkUrl.set(null);
    this.paymentLinkError.set(null);
    this.loadCreditNotes(invoice.invoice_id);
  }

  clearSelection(): void {
    this.selectedInvoice.set(null);
    this.creditNotes.set([]);
  }

  private can(permission: string): boolean {
    return this.permissions()?.permissions?.has(permission) ?? false;
  }

  private loadCreditNotes(invoiceId: string): void {
    this.creditNotes.set([]);
    this.invoiceService.listCreditNotes(invoiceId).subscribe({
      next: (notes) => this.creditNotes.set(notes),
      error: () => this.creditNotes.set([]),
    });
  }

  /** Refresh the open invoice and its row after a payment or refund. */
  private replaceInvoice(updated: InvoiceResponse): void {
    this.selectedInvoice.set(updated);
    this.invoices.update((rows) =>
      rows.map((row) => (row.invoice_id === updated.invoice_id ? updated : row)),
    );
  }

  openPaymentDrawer(): void {
    const inv = this.selectedInvoice();
    if (!inv) return;
    this.paymentForm.reset({ method: 'cash', amount: inv.balance_due ?? '', reference: '' });
    this.applyReferenceRule('cash');
    this.paymentDrawerVisible.set(true);
  }

  private applyReferenceRule(method: StaffPaymentMethod): void {
    const required = REFERENCE_REQUIRED.has(method);
    this.referenceRequired.set(required);
    const control = this.paymentForm.controls.reference;
    control.setValidators(
      required ? [Validators.required, Validators.maxLength(100)] : [Validators.maxLength(100)],
    );
    control.updateValueAndValidity();
  }

  protected submitPayment(): void {
    const inv = this.selectedInvoice();
    if (!inv || this.paymentForm.invalid) {
      this.paymentForm.markAllAsTouched();
      return;
    }
    const value = this.paymentForm.getRawValue();
    this.submitting.set(true);
    this.invoiceService
      .recordPayment(inv.invoice_id, {
        method: value.method,
        amount: value.amount,
        reference: value.reference,
      })
      .subscribe({
        next: (updated) => {
          this.submitting.set(false);
          this.paymentDrawerVisible.set(false);
          this.replaceInvoice(updated);
          this.messageService.add({
            severity: 'success',
            summary: 'Payment recorded',
            detail: `${formatCurrencyInr(value.amount)} recorded against ${updated.invoice_number ?? 'the invoice'}.`,
          });
        },
        error: () => this.submitting.set(false),
      });
  }

  protected sendPaymentLink(): void {
    const inv = this.selectedInvoice();
    if (!inv) return;
    this.submitting.set(true);
    this.paymentLinkUrl.set(null);
    this.paymentLinkError.set(null);
    this.invoiceService.createPaymentLink(inv.order_id).subscribe({
      next: (link) => {
        this.submitting.set(false);
        this.paymentLinkUrl.set(link.payment_url);
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        const status = (error as { status?: number } | null)?.status;
        this.paymentLinkError.set(
          status === 503
            ? 'Online payments are not set up for this agency yet. Record the payment manually, or ask an admin to configure Razorpay.'
            : 'The payment link could not be created.',
        );
      },
    });
  }

  protected copyPaymentLink(): void {
    const url = this.paymentLinkUrl();
    if (!url) return;
    void navigator.clipboard
      ?.writeText(url)
      .then(() =>
        this.messageService.add({ severity: 'success', summary: 'Link copied', detail: url }),
      );
  }

  protected openRefundDrawer(): void {
    const inv = this.selectedInvoice();
    if (!inv) return;
    this.refundForm.reset({ amount: inv.amount_paid ?? '', reason: '' });
    this.refundDrawerVisible.set(true);
  }

  protected submitRefund(): void {
    const inv = this.selectedInvoice();
    if (!inv || this.refundForm.invalid) {
      this.refundForm.markAllAsTouched();
      return;
    }
    const value = this.refundForm.getRawValue();
    this.submitting.set(true);
    this.invoiceService.requestRefund(inv.invoice_id, value.amount, value.reason).subscribe({
      next: (note) => {
        this.submitting.set(false);
        this.refundDrawerVisible.set(false);
        this.creditNotes.update((notes) => [note, ...notes]);
        this.messageService.add({
          severity: 'success',
          summary: 'Refund requested',
          detail: 'A manager must approve the credit note before it takes effect.',
        });
      },
      error: () => this.submitting.set(false),
    });
  }

  protected approveCreditNote(note: CreditNoteResponse): void {
    const inv = this.selectedInvoice();
    if (!inv) return;
    this.submitting.set(true);
    this.invoiceService.approveRefund(inv.invoice_id, note.id).subscribe({
      next: (approved) => {
        this.submitting.set(false);
        this.creditNotes.update((notes) => notes.map((n) => (n.id === approved.id ? approved : n)));
        this.invoiceService.get(inv.invoice_id).subscribe((fresh) => this.replaceInvoice(fresh));
      },
      error: () => this.submitting.set(false),
    });
  }

  printPdf(): void {
    const inv = this.selectedInvoice();
    if (!inv) return;
    this.isPrinting.set(true);
    this.printingService.printInvoicePdf(inv.invoice_id).subscribe({
      next: () => this.isPrinting.set(false),
      error: () => this.isPrinting.set(false),
    });
  }

  printThermal(): void {
    const inv = this.selectedInvoice();
    if (!inv) return;
    this.isPrinting.set(true);
    this.printingService.printInvoiceThermal(inv.invoice_id).subscribe({
      next: (res) => {
        this.isPrinting.set(false);
        this.thermalReceiptUrl.set(res.download_url);
        this.showThermalDialog.set(true);
      },
      error: () => {
        this.isPrinting.set(false);
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to generate the thermal receipt.',
        });
      },
    });
  }

  /** The embedded iframe's own toolbar hides itself once it detects it's
   * framed (see `render_invoice_thermal_html` on the backend). This
   * dialog-level button triggers its `window.print()` via `postMessage`
   * instead of calling `contentWindow.print()` directly — the iframe is
   * cross-origin (served from object storage, not this app's origin), and
   * only a small allowlist of properties (postMessage included) is
   * reachable on a cross-origin window; `.print()` throws a SecurityError. */
  protected printThermalReceipt(): void {
    this.thermalFrame()?.nativeElement.contentWindow?.postMessage(
      { type: 'lpg-thermal-receipt-print' },
      '*',
    );
  }

  /** Escape hatch alongside the embedded preview — some browsers/printer
   * setups behave more predictably with the receipt in its own tab. */
  protected openThermalReceiptInNewTab(): void {
    const url = this.thermalReceiptUrl();
    if (url) window.open(url, '_blank');
  }

  protected closeThermalDialog(): void {
    this.showThermalDialog.set(false);
    this.thermalReceiptUrl.set(null);
  }

  protected openCustomerPreview(customerId: string): void {
    const dialog = this.customerPreviewDialog();
    dialog.open();
    this.customerService.get(customerId).subscribe({
      next: (customer) => dialog.showData(this.customerPreviewData(customer)),
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

  private customerPreviewData(customer: CustomerResponse): PreviewData {
    const address = this.customerPreviewAddress(customer);
    return {
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
    };
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

  protected openOrderPreview(orderId: string): void {
    this.showOrderPreview.set(true);
    this.orderPreviewLoading.set(true);
    this.orderPreview.set(null);
    this.orderService.getOrder(orderId).subscribe({
      next: (order) => {
        this.orderPreview.set(order);
        this.orderPreviewLoading.set(false);
      },
      error: () => {
        this.orderPreviewLoading.set(false);
        this.showOrderPreview.set(false);
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'That order could not be found.',
        });
      },
    });
  }
}
