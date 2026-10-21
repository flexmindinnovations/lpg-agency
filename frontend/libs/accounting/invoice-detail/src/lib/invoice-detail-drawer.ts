import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  effect,
  inject,
  model,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DomSanitizer, type SafeResourceUrl } from '@angular/platform-browser';
import { ButtonDirective } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { Drawer } from 'primeng/drawer';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { MessageService } from 'primeng/api';
import {
  DrawerA11yDirective,
  FormFieldComponent,
  PreviewDialog,
  type PreviewData,
  type ChipSeverity,
  bookingSourceLabel,
  formatCurrencyInr,
  toSentenceCase,
} from '@lpg/shared/ui';
import { LpgDatePipe, LpgDateTimePipe, PERMISSION_CHECKER } from '@lpg/shared/util';
import {
  AdminCylinderTypeService,
  CustomerService,
  InvoiceService,
  OrderService,
  PrintingService,
  type CreditNoteResponse,
  type CustomerResponse,
  type CylinderTypeResponse,
  type InvoiceResponse,
  type OrderResponse,
  type StaffPaymentMethod,
} from '@lpg/shared/data-access';
import { invoiceStatusLabel, invoiceStatusSeverity } from './invoice-status';

/** Methods that must carry a reference the accountant can match against
 * the bank statement — mirrors the backend rule. */
const REFERENCE_REQUIRED: ReadonlySet<StaffPaymentMethod> = new Set(['cheque', 'bank_transfer']);

/**
 * The invoice details drawer: lines, GST, payments, credit notes, and the
 * payment, refund, payment-link, send and print actions. Used by the Invoices
 * page and the order page, so both show the same drawer.
 *
 * Bind `[(invoice)]`: a non-null invoice opens the drawer; closing it sets the
 * model back to null. `(invoiceUpdated)` fires after a payment or approved
 * refund so the host can refresh its own copy (a list row, an order card).
 */
@Component({
  selector: 'lpg-invoice-detail-drawer',
  standalone: true,
  imports: [
    DrawerA11yDirective,
    Drawer,
    Dialog,
    InputText,
    Tag,
    ButtonDirective,
    PreviewDialog,
    LpgDatePipe,
    LpgDateTimePipe,
    CurrencyPipe,
    ReactiveFormsModule,
    Select,
    Message,
    FormFieldComponent,
  ],
  templateUrl: './invoice-detail-drawer.html',
  styleUrl: './invoice-detail-drawer.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InvoiceDetailDrawer implements OnInit {
  private readonly invoiceService = inject(InvoiceService);
  private readonly printingService = inject(PrintingService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly customerService = inject(CustomerService);
  private readonly orderService = inject(OrderService);
  private readonly permissions = inject(PERMISSION_CHECKER);
  private readonly fb = inject(FormBuilder);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly messageService = inject(MessageService);

  /** The open invoice; null keeps the drawer closed. */
  readonly invoice = model<InvoiceResponse | null>(null);
  /** A payment or approved refund changed the invoice. */
  readonly invoiceUpdated = output<InvoiceResponse>();

  /** Which print button is working; only that one shows a spinner. */
  protected readonly printingFormat = signal<'pdf' | 'thermal' | null>(null);
  protected readonly isSending = signal(false);
  private readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);

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
  // away and lose the invoice context. Customer preview renders through the
  // shared `PreviewDialog`; Order preview keeps its own dialog since it has
  // a line item list that doesn't fit the shared component's field grid.
  protected readonly customerPreviewDialog =
    viewChild.required<PreviewDialog>('customerPreviewDialog');

  protected readonly showOrderPreview = signal(false);
  protected readonly orderPreview = signal<OrderResponse | null>(null);
  protected readonly orderPreviewLoading = signal(false);

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
  protected readonly invoiceStatusLabel = invoiceStatusLabel;
  protected readonly invoiceStatusSeverity = invoiceStatusSeverity;

  protected orderStatusSeverity(status: string): ChipSeverity {
    return InvoiceDetailDrawer.ORDER_STATUS_SEVERITY[status] ?? 'secondary';
  }

  protected readonly paymentMethodLabel = (method: string): string =>
    this.paymentMethodOptions.find((o) => o.value === method)?.label ??
    (method === 'online_gateway' ? 'Online (Razorpay)' : toSentenceCase(method));

  protected readonly placeOfSupply = (inv: InvoiceResponse): string =>
    inv.place_of_supply_state_code ?? '—';

  constructor() {
    this.paymentForm.controls.method.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((method) => this.applyReferenceRule(method));
    // A different invoice opened: start from a clean slate and load its
    // credit notes. Payments on the same invoice keep the link/notes shown.
    let openId: string | null = null;
    effect(() => {
      const id = this.invoice()?.invoice_id ?? null;
      if (id === openId) return;
      openId = id;
      untracked(() => {
        this.paymentLinkUrl.set(null);
        this.paymentLinkError.set(null);
        this.creditNotes.set([]);
        if (id) this.loadCreditNotes(id);
      });
    });
  }

  ngOnInit(): void {
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (types) => this.cylinderTypes.set(types),
    });
  }

  protected close(): void {
    this.invoice.set(null);
  }

  private can(permission: string): boolean {
    return this.permissions()?.permissions?.has(permission) ?? false;
  }

  private loadCreditNotes(invoiceId: string): void {
    this.invoiceService.listCreditNotes(invoiceId).subscribe({
      next: (notes) => this.creditNotes.set(notes),
      error: () => this.creditNotes.set([]),
    });
  }

  /** Refresh the open invoice and tell the host after a payment or refund. */
  private replaceInvoice(updated: InvoiceResponse): void {
    this.invoice.set(updated);
    this.invoiceUpdated.emit(updated);
  }

  protected sendToCustomer(): void {
    const inv = this.invoice();
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

  openPaymentDrawer(): void {
    const inv = this.invoice();
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
    const inv = this.invoice();
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
    const inv = this.invoice();
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
    const inv = this.invoice();
    if (!inv) return;
    this.refundForm.reset({ amount: inv.amount_paid ?? '', reason: '' });
    this.refundDrawerVisible.set(true);
  }

  protected submitRefund(): void {
    const inv = this.invoice();
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
    const inv = this.invoice();
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

  protected printPdf(): void {
    const inv = this.invoice();
    if (!inv || this.printingFormat()) return;
    // Open the tab inside the click so pop-up blockers allow it.
    const tab = this.printingService.openPendingTab();
    this.printingFormat.set('pdf');
    this.printingService.renderInvoice(inv.invoice_id, 'pdf').subscribe({
      next: (blob) => {
        this.printingFormat.set(null);
        this.printingService.showInTab(blob, tab, `${inv.invoice_number ?? 'invoice'}.pdf`);
      },
      // The failed POST already toasts the server's message.
      error: () => {
        this.printingFormat.set(null);
        tab?.close();
      },
    });
  }

  protected printThermal(): void {
    const inv = this.invoice();
    if (!inv || this.printingFormat()) return;
    this.printingFormat.set('thermal');
    this.printingService.renderInvoice(inv.invoice_id, 'thermal').subscribe({
      next: (blob) => {
        this.printingFormat.set(null);
        this.releaseThermalReceipt();
        this.thermalReceiptUrl.set(URL.createObjectURL(blob));
        this.showThermalDialog.set(true);
      },
      error: () => this.printingFormat.set(null),
    });
  }

  /** The receipt is a blob URL created by this page, so the preview iframe is
   * same-origin and can be printed directly. If a browser still refuses, the
   * receipt page's own handler prints on a postMessage. */
  protected printThermalReceipt(): void {
    const frame = this.thermalFrame()?.nativeElement.contentWindow;
    if (!frame) return;
    try {
      frame.focus();
      frame.print();
    } catch {
      frame.postMessage({ type: 'lpg-thermal-receipt-print' }, '*');
    }
  }

  /** Escape hatch alongside the embedded preview — some browsers/printer
   * setups behave more predictably with the receipt in its own tab. */
  protected openThermalReceiptInNewTab(): void {
    const url = this.thermalReceiptUrl();
    if (url) window.open(url, '_blank');
  }

  private releaseThermalReceipt(): void {
    const url = this.thermalReceiptUrl();
    if (url) URL.revokeObjectURL(url);
    this.thermalReceiptUrl.set(null);
  }

  protected closeThermalDialog(): void {
    this.showThermalDialog.set(false);
    this.releaseThermalReceipt();
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
          severity: InvoiceDetailDrawer.CUSTOMER_STATUS_SEVERITY[customer.status] ?? 'secondary',
        },
        {
          label: 'KYC: ' + toSentenceCase(customer.kyc_status),
          severity: InvoiceDetailDrawer.KYC_STATUS_SEVERITY[customer.kyc_status] ?? 'secondary',
        },
      ],
      fields: [
        { label: 'Phone', value: customer.phone_number },
        { label: 'Customer Type', value: toSentenceCase(customer.customer_type) },
      ],
      fullWidthFields: address ? [{ label: 'Address', value: address }] : [],
    };
  }

  private customerPreviewAddress(customer: CustomerResponse): string | null {
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
