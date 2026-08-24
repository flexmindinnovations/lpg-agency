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
import { DatePipe, CurrencyPipe } from '@angular/common';
import { DomSanitizer, type SafeResourceUrl } from '@angular/platform-browser';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { IconField } from 'primeng/iconfield';
import { Tag } from 'primeng/tag';
import { Drawer } from 'primeng/drawer';
import { Dialog } from 'primeng/dialog';
import { ButtonDirective } from 'primeng/button';
import { MessageService } from 'primeng/api';
import { DataGridComponent, type DataGridColumn, PreviewDialog, type PreviewData, StatusChipCell, type ChipSeverity, toSentenceCase, shortId } from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  AdminCylinderTypeService,
  CustomerService,
  InvoiceService,
  OrderService,
  PrintingService,
  type CustomerResponse,
  type CylinderTypeResponse,
  type InvoiceResponse,
  type OrderResponse,
} from '@lpg/shared/data-access';

@Component({
  selector: 'lpg-feature-invoices',
  standalone: true,
  imports: [
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
    DatePipe,
    CurrencyPipe,
  ],
  templateUrl: './feature-invoices.html',
  styleUrl: './feature-invoices.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeatureInvoices implements OnInit {
  private readonly invoiceService = inject(InvoiceService);
  private readonly printingService = inject(PrintingService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly customerService = inject(CustomerService);
  private readonly orderService = inject(OrderService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly messageService = inject(MessageService);

  readonly isLoading = signal(false);
  readonly isPrinting = signal(false);
  readonly invoices = signal<InvoiceResponse[]>([]);
  readonly selectedInvoice = signal<InvoiceResponse | null>(null);
  private readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);

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
  protected readonly customerPreviewDialog = viewChild.required<PreviewDialog>('customerPreviewDialog');

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
      valueFormatter: (val, row) => (val as string | null) ?? shortId(row.invoice_id),
    },
    { field: 'issued_at', header: 'Date', sortable: true, valueFormatter: (val) => new Date(val as string).toLocaleDateString() },
    {
      field: 'customer_consumer_number',
      header: 'Customer',
      sortable: false,
      valueFormatter: (val, row) => (val as string | null) ?? shortId(row.customer_id),
    },
    { field: 'total_amount', header: 'Total Amount', sortable: true, numeric: true, valueFormatter: (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(val)) },
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

  ngOnInit(): void {
    this.loadInvoices();
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (types) => this.cylinderTypes.set(types),
    });
  }

  loadInvoices(): void {
    this.isLoading.set(true);
    this.invoiceService.list(1, 100).subscribe({
      next: (res) => {
        this.invoices.set(res.items);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
      },
    });
  }

  onInvoiceSelected(invoice: InvoiceResponse): void {
    this.selectedInvoice.set(invoice);
  }

  clearSelection(): void {
    this.selectedInvoice.set(null);
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
        { label: toSentenceCase(customer.status), severity: this.customerStatusSeverity(customer.status) },
        { label: 'KYC: ' + toSentenceCase(customer.kyc_status), severity: this.kycStatusSeverity(customer.kyc_status) },
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
    return [address.line_1, address.line_2, address.area, address.city, address.state, address.pincode]
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
