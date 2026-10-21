import { Component, computed, inject, viewChild } from '@angular/core';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  formatCurrencyInr,
  formatReportDate,
} from '@lpg/shared/ui';
import {
  ReportingStore,
  type DailySalesRecord,
  type ReportFilter,
} from '@lpg/reporting/data-access';
import { ReportFilters } from '../report-filters/report-filters';

@Component({
  selector: 'lib-daily-sales',
  standalone: true,
  imports: [DataGridComponent, EmptyStateComponent, ReportFilters],
  templateUrl: './daily-sales.html',
  styleUrl: './daily-sales.css',
})
export class DailySales {
  store = inject(ReportingStore);
  private readonly grid = viewChild(DataGridComponent);

  /** One row per day *and branch* (DA-11): the branch column says which. */
  protected readonly columns: DataGridColumn<DailySalesRecord>[] = [
    { field: 'sale_date', header: 'Date', valueFormatter: formatReportDate },
    {
      field: 'branch_name',
      header: 'Branch',
      valueFormatter: (v) => (v as string | null) ?? 'No branch',
    },
    { field: 'total_invoices', header: 'Invoices', numeric: true },
    {
      field: 'taxable_value',
      header: 'Taxable value',
      numeric: true,
      valueFormatter: formatCurrencyInr,
    },
    { field: 'total_tax', header: 'GST', numeric: true, valueFormatter: formatCurrencyInr },
    {
      field: 'total_revenue',
      header: 'Revenue',
      numeric: true,
      valueFormatter: formatCurrencyInr,
    },
  ];

  protected readonly totals = computed(() =>
    this.store.dailySales().reduce(
      (sum, row) => ({
        invoices: sum.invoices + row.total_invoices,
        taxable: sum.taxable + Number(row.taxable_value ?? 0),
        tax: sum.tax + Number(row.total_tax),
        revenue: sum.revenue + Number(row.total_revenue),
      }),
      { invoices: 0, taxable: 0, tax: 0, revenue: 0 },
    ),
  );

  protected readonly formatCurrencyInr = formatCurrencyInr;

  protected load(filter: ReportFilter): void {
    this.store.loadDailySales(filter);
  }

  protected exportCsv(): void {
    const { startDate, endDate } = this.store.filter();
    this.grid()?.exportCsv(`daily-sales-${startDate}-to-${endDate}`);
  }
}
