import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listInvoicesApiV1InvoicesGet } from './generated/fn/invoices/list-invoices-api-v-1-invoices-get';
import { getInvoiceApiV1InvoicesInvoiceIdGet } from './generated/fn/invoices/get-invoice-api-v-1-invoices-invoice-id-get';
import type { InvoicePageResponse } from './generated/models/invoice-page-response';
import type { InvoiceResponse } from './generated/models/invoice-response';

@Injectable({ providedIn: 'root' })
export class InvoiceService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  list(page = 1, page_size = 100, customerId?: string, orderId?: string, status?: 'draft' | 'finalized' | 'cancelled'): Observable<InvoicePageResponse> {
    return listInvoicesApiV1InvoicesGet(this.http, this.config.rootUrl, {
      page,
      page_size,
      customer_id: customerId,
      order_id: orderId,
      status: status
    }).pipe(map((res) => res.body));
  }

  get(invoiceId: string): Observable<InvoiceResponse> {
    return getInvoiceApiV1InvoicesInvoiceIdGet(this.http, this.config.rootUrl, {
      invoice_id: invoiceId,
    }).pipe(map((res) => res.body));
  }
}
