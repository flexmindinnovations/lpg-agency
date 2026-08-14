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
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { InvoiceService, type InvoiceResponse } from '@lpg/shared/data-access';

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

  readonly isLoading = signal(false);
  readonly invoices = signal<InvoiceResponse[]>([]);
  readonly selectedInvoice = signal<InvoiceResponse | null>(null);

  readonly columns: DataGridColumn<InvoiceResponse>[] = [
    { field: 'invoice_id', header: 'Invoice #', sortable: true, onLinkClick: (row) => this.onInvoiceSelected(row) },
    { field: 'issued_at', header: 'Date', sortable: true, valueFormatter: (val) => new Date(val as string).toLocaleDateString() },
    { field: 'customer_id', header: 'Customer', sortable: false },
    { field: 'total_amount', header: 'Total Amount', sortable: true, numeric: true, valueFormatter: (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(val)) },
    { field: 'status', header: 'Status', sortable: true, valueFormatter: (val) => String(val).toUpperCase() },
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
}
