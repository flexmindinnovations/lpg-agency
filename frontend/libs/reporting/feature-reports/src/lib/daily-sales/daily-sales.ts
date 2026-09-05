import { Component, inject, OnInit } from '@angular/core';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  formatCurrencyInr,
  formatReportDate,
} from '@lpg/shared/ui';
import { ReportingStore, type DailySalesRecord } from '@lpg/reporting/data-access';

@Component({
  selector: 'lib-daily-sales',
  standalone: true,
  imports: [DataGridComponent, EmptyStateComponent],
  templateUrl: './daily-sales.html',
  styleUrl: './daily-sales.css',
})
export class DailySales implements OnInit {
  store = inject(ReportingStore);

  protected readonly columns: DataGridColumn<DailySalesRecord>[] = [
    { field: 'sale_date', header: 'Date', width: 160, valueFormatter: formatReportDate },
    { field: 'total_invoices', header: 'Total Invoices', numeric: true, width: 160 },
    { field: 'total_revenue', header: 'Total Revenue', numeric: true, valueFormatter: formatCurrencyInr },
    { field: 'total_tax', header: 'Total Tax', numeric: true, valueFormatter: formatCurrencyInr },
  ];

  ngOnInit() {
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);
    this.store.loadDailySales({
      startDate: thirtyDaysAgo.toISOString().split('T')[0],
      endDate: today.toISOString().split('T')[0],
    });
  }
}
