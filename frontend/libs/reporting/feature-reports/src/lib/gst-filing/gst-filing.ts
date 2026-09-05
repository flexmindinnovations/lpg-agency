import { Component, inject, OnInit } from '@angular/core';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  formatCurrencyInr,
} from '@lpg/shared/ui';
import { ReportingStore, type GstFilingRecord } from '@lpg/reporting/data-access';

@Component({
  selector: 'lib-gst-filing',
  standalone: true,
  imports: [DataGridComponent, EmptyStateComponent],
  templateUrl: './gst-filing.html',
  styleUrl: './gst-filing.css',
})
export class GstFiling implements OnInit {
  store = inject(ReportingStore);

  protected readonly columns: DataGridColumn<GstFilingRecord>[] = [
    { field: 'filing_period', header: 'Filing Period', flex: 1, sortable: true },
    { field: 'total_gst', header: 'Total GST', numeric: true, width: 200, valueFormatter: formatCurrencyInr },
  ];

  ngOnInit() {
    this.store.loadGstFiling();
  }
}
