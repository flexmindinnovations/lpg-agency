import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableModule } from 'primeng/table';
import { ReportingStore } from '@lpg/reporting/data-access';

@Component({
  selector: 'lib-gst-filing',
  standalone: true,
  imports: [CommonModule, TableModule],
  templateUrl: './gst-filing.html',
  styleUrl: './gst-filing.css',
})
export class GstFiling implements OnInit {
  store = inject(ReportingStore);

  ngOnInit() {
    this.store.loadGstFiling();
  }
}
