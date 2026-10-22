import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, debounceTime } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { IconField } from 'primeng/iconfield';
import {
  DateRangeFilterComponent,
  ExportButtonComponent,
  type DateRangeValue,
  PageHeaderComponent,
} from '@lpg/shared/ui';
import { Dialog } from 'primeng/dialog';
import { ButtonDirective } from 'primeng/button';
import { Select } from 'primeng/select';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import {
  DataGridComponent,
  type DataGridColumn,
  StatusChipCell,
  formatCurrencyInr,
} from '@lpg/shared/ui';
import { LpgDatePipe, PERMISSION_CHECKER, formatDisplayDate } from '@lpg/shared/util';
import {
  INVOICE_STATUS_LABEL,
  INVOICE_STATUS_SEVERITY,
  InvoiceDetailDrawer,
} from '@lpg/accounting/invoice-detail';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  InvoiceService,
  errorMessageFor,
  type InvoiceResponse,
  type UninvoicedOrderResponse,
} from '@lpg/shared/data-access';

@Component({
  selector: 'lpg-feature-invoices',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    Dialog,
    InputIcon,
    InputText,
    IconField,
    ButtonDirective,
    DataGridComponent,
    InvoiceDetailDrawer,
    LpgDatePipe,
    CurrencyPipe,
    FormsModule,
    Select,
    RouterLink,
    DateRangeFilterComponent,
    ExportButtonComponent,
  ],
  templateUrl: './feature-invoices.html',
  styleUrl: './feature-invoices.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeatureInvoices implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly invoiceService = inject(InvoiceService);
  private readonly permissions = inject(PERMISSION_CHECKER);
  private readonly messageService = inject(MessageService);

  readonly isLoading = signal(false);
  readonly loadError = signal<string | null>(null);
  readonly invoices = signal<InvoiceResponse[]>([]);
  readonly selectedInvoice = signal<InvoiceResponse | null>(null);
  readonly searchQuery = signal('');

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
    { label: 'Unpaid', value: 'issued' },
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
        severityMap: INVOICE_STATUS_SEVERITY,
        labelMap: INVOICE_STATUS_LABEL,
      },
    },
  ];

  constructor() {
    this.searchChanges.pipe(debounceTime(300), takeUntilDestroyed()).subscribe((query) => {
      this.searchQuery.set(query);
      this.page.set(1);
      this.loadInvoices();
    });
  }

  ngOnInit(): void {
    this.openLinkedInvoice();
    this.loadInvoices();
    this.loadHeldOrders();
  }

  /** `/invoices?invoice=<id>` (from an order page) opens that invoice. */
  private openLinkedInvoice(): void {
    const id = this.route.snapshot.queryParamMap.get('invoice');
    if (!id) return;
    this.invoiceService.get(id).subscribe({
      next: (invoice) => this.onInvoiceSelected(invoice),
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
  }

  /** A payment or refund in the drawer changed the invoice: refresh its row. */
  protected onInvoiceUpdated(updated: InvoiceResponse): void {
    this.invoices.update((rows) =>
      rows.map((row) => (row.invoice_id === updated.invoice_id ? updated : row)),
    );
  }

  private can(permission: string): boolean {
    return this.permissions()?.permissions?.has(permission) ?? false;
  }
}
