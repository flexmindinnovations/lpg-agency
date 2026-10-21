import { Component, inject, viewChild } from '@angular/core';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  formatCurrencyInr,
  formatPercent,
  formatReportDate,
} from '@lpg/shared/ui';
import {
  ReportingStore,
  type DriverPerformanceRecord,
  type ReportFilter,
} from '@lpg/reporting/data-access';
import { ReportFilters } from '../report-filters/report-filters';

@Component({
  selector: 'lib-driver-performance',
  standalone: true,
  imports: [DataGridComponent, EmptyStateComponent, ReportFilters],
  templateUrl: './driver-performance.html',
  styleUrl: './driver-performance.css',
})
export class DriverPerformance {
  store = inject(ReportingStore);
  private readonly grid = viewChild(DataGridComponent);

  protected readonly columns: DataGridColumn<DriverPerformanceRecord>[] = [
    {
      field: 'driver_name',
      header: 'Driver',
      flex: 2,
      valueFormatter: (v, row) =>
        row.employee_code ? `${v as string} (${row.employee_code})` : (v as string),
    },
    {
      field: 'branch_name',
      header: 'Branch',
      valueFormatter: (v) => (v as string | null) ?? '—',
    },
    { field: 'date', header: 'Date', valueFormatter: formatReportDate },
    { field: 'total_stops', header: 'Stops', numeric: true },
    { field: 'delivered_stops', header: 'Delivered', numeric: true },
    { field: 'failed_stops', header: 'Failed', numeric: true },
    {
      field: 'cash_expected',
      header: 'Cash due',
      numeric: true,
      valueFormatter: formatCurrencyInr,
    },
    {
      field: 'cash_handed_over',
      header: 'Handed over',
      numeric: true,
      valueFormatter: (v) => (v == null ? 'Not declared' : formatCurrencyInr(v)),
    },
    {
      field: 'cash_accuracy',
      header: 'Cash accuracy',
      numeric: true,
      valueFormatter: (v) => (v == null ? '—' : formatPercent(v, 1)),
    },
  ];

  protected load(filter: ReportFilter): void {
    this.store.loadDriverPerformance(filter);
  }

  protected exportCsv(): void {
    const { startDate, endDate } = this.store.filter();
    this.grid()?.exportCsv(`driver-performance-${startDate}-to-${endDate}`);
  }
}
