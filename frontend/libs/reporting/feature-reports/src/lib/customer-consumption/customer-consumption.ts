import { Component, inject, OnInit } from '@angular/core';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  formatDecimal,
} from '@lpg/shared/ui';
import { ReportingStore, type CustomerConsumptionRecord } from '@lpg/reporting/data-access';

@Component({
  selector: 'lib-customer-consumption',
  standalone: true,
  imports: [DataGridComponent, EmptyStateComponent],
  templateUrl: './customer-consumption.html',
  styleUrl: './customer-consumption.css',
})
export class CustomerConsumption implements OnInit {
  store = inject(ReportingStore);

  protected readonly columns: DataGridColumn<CustomerConsumptionRecord>[] = [
    { field: 'customer_name', header: 'Customer', flex: 1, sortable: true, filterable: true },
    {
      field: 'avg_refill_interval_days',
      header: 'Avg Refill Interval (days)',
      numeric: true,
      width: 240,
      valueFormatter: (v) => formatDecimal(v, 1),
    },
  ];

  ngOnInit() {
    this.store.loadCustomerConsumption();
  }
}
