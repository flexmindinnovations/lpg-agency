import { Component, inject, OnInit } from '@angular/core';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  formatPercent,
  formatReportDate,
} from '@lpg/shared/ui';
import { ReportingStore, type DriverPerformanceRecord } from '@lpg/reporting/data-access';

@Component({
  selector: 'lib-driver-performance',
  standalone: true,
  imports: [DataGridComponent, EmptyStateComponent],
  templateUrl: './driver-performance.html',
  styleUrl: './driver-performance.css',
})
export class DriverPerformance implements OnInit {
  store = inject(ReportingStore);

  protected readonly columns: DataGridColumn<DriverPerformanceRecord>[] = [
    { field: 'date', header: 'Date', width: 160, valueFormatter: formatReportDate },
    { field: 'total_stops', header: 'Total Stops', numeric: true, width: 140 },
    { field: 'delivered_stops', header: 'Delivered Stops', numeric: true, width: 160 },
    {
      field: 'cash_accuracy',
      header: 'Cash Accuracy',
      numeric: true,
      width: 160,
      valueFormatter: (v) => formatPercent(v, 2),
    },
  ];

  ngOnInit() {
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);
    this.store.loadDriverPerformance({
      startDate: thirtyDaysAgo.toISOString().split('T')[0],
      endDate: today.toISOString().split('T')[0],
    });
  }
}
