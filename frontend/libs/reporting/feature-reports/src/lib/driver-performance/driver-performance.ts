import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableModule } from 'primeng/table';
import { ReportingStore } from '@lpg/reporting/data-access';

@Component({
  selector: 'lib-driver-performance',
  standalone: true,
  imports: [CommonModule, TableModule],
  templateUrl: './driver-performance.html',
  styleUrl: './driver-performance.css',
})
export class DriverPerformance implements OnInit {
  store = inject(ReportingStore);

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
