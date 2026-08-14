import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableModule } from 'primeng/table';
import { ReportingStore } from '@lpg/reporting/data-access';

@Component({
  selector: 'lib-customer-consumption',
  standalone: true,
  imports: [CommonModule, TableModule],
  templateUrl: './customer-consumption.html',
  styleUrl: './customer-consumption.css',
})
export class CustomerConsumption implements OnInit {
  store = inject(ReportingStore);

  ngOnInit() {
    this.store.loadCustomerConsumption();
  }
}
