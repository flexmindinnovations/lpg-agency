import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { DatePipe, CurrencyPipe } from '@angular/common';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { IconField } from 'primeng/iconfield';
import { Tag } from 'primeng/tag';
import { Drawer } from 'primeng/drawer';
import { ButtonDirective } from 'primeng/button';
import { DataGridComponent, type DataGridColumn, StatusChipCell } from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { InvoiceService, PrintingService, type InvoiceResponse } from '@lpg/shared/data-access';

@Component({
  selector: 'lpg-feature-invoices',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    Drawer,
    InputIcon,
    InputText,
    IconField,
    Tag,
    ButtonDirective,
    DataGridComponent,
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

  readonly isLoading = signal(false);
  readonly isPrinting = signal(false);
  readonly invoices = signal<InvoiceResponse[]>([]);
  readonly selectedInvoice = signal<InvoiceResponse | null>(null);

  readonly columns: DataGridColumn<InvoiceResponse>[] = [
    { field: 'invoice_id', header: 'Invoice #', sortable: true, onLinkClick: (row) => this.onInvoiceSelected(row) },
    { field: 'issued_at', header: 'Date', sortable: true, valueFormatter: (val) => new Date(val as string).toLocaleDateString() },
    { field: 'customer_id', header: 'Customer', sortable: false },
    { field: 'total_amount', header: 'Total Amount', sortable: true, numeric: true, valueFormatter: (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(val)) },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        severityMap: {
          draft: 'secondary',
          issued: 'info',
          partially_paid: 'warn',
          paid: 'success',
          cancelled: 'danger',
          refunded: 'danger',
        },
      },
    },
  ];

  ngOnInit(): void {
    this.loadInvoices();
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
      next: () => this.isPrinting.set(false),
      error: () => this.isPrinting.set(false),
    });
  }
}
