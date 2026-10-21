import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listInvoicesApiV1InvoicesGet } from './generated/fn/invoices/list-invoices-api-v-1-invoices-get';
import { getInvoiceApiV1InvoicesInvoiceIdGet } from './generated/fn/invoices/get-invoice-api-v-1-invoices-invoice-id-get';
import { recordPaymentApiV1InvoicesInvoiceIdPaymentsPost } from './generated/fn/invoices/record-payment-api-v-1-invoices-invoice-id-payments-post';
import { listUninvoicedOrdersApiV1InvoicesUninvoicedOrdersGet } from './generated/fn/invoices/list-uninvoiced-orders-api-v-1-invoices-uninvoiced-orders-get';
import { sendInvoiceApiV1InvoicesInvoiceIdSendPost } from './generated/fn/invoices/send-invoice-api-v-1-invoices-invoice-id-send-post';
import { issueInvoiceApiV1InvoicesPost } from './generated/fn/invoices/issue-invoice-api-v-1-invoices-post';
import { listCreditNotesApiV1InvoicesInvoiceIdCreditNotesGet } from './generated/fn/invoices/list-credit-notes-api-v-1-invoices-invoice-id-credit-notes-get';
import { requestRefundApiV1InvoicesInvoiceIdRefundsPost } from './generated/fn/invoices/request-refund-api-v-1-invoices-invoice-id-refunds-post';
import { approveRefundApiV1InvoicesInvoiceIdRefundsCreditNoteIdApprovePost } from './generated/fn/invoices/approve-refund-api-v-1-invoices-invoice-id-refunds-credit-note-id-approve-post';
import { createPaymentLinkApiV1OrdersOrderIdPaymentLinksPost } from './generated/fn/online-payments/create-payment-link-api-v-1-orders-order-id-payment-links-post';
import type { InvoicePageResponse } from './generated/models/invoice-page-response';
import type { InvoiceResponse } from './generated/models/invoice-response';
import type { UninvoicedOrderResponse } from './generated/models/uninvoiced-order-response';
import type { CreditNoteResponse } from './generated/models/credit-note-response';
import type { OnlinePaymentResponse } from './generated/models/online-payment-response';

/** Payment methods office staff can record against an invoice (DA-07). */
export type StaffPaymentMethod = 'cash' | 'upi' | 'card' | 'cheque' | 'bank_transfer';

export interface InvoiceListFilter {
  readonly page: number;
  readonly pageSize: number;
  readonly status?: string | null;
  /** IST calendar days, `YYYY-MM-DD`, inclusive. */
  readonly issuedFrom?: string | null;
  readonly issuedTo?: string | null;
  /** Invoice, order or consumer number, or customer name. */
  readonly search?: string | null;
  readonly customerId?: string | null;
  readonly orderId?: string | null;
}

export interface RecordPaymentInput {
  readonly method: StaffPaymentMethod;
  readonly amount: string;
  readonly reference?: string | null;
}

@Injectable({ providedIn: 'root' })
export class InvoiceService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  list(filter: InvoiceListFilter): Observable<InvoicePageResponse> {
    return listInvoicesApiV1InvoicesGet(this.http, this.config.rootUrl, {
      page: filter.page,
      page_size: filter.pageSize,
      status: filter.status || undefined,
      issued_from: filter.issuedFrom || undefined,
      issued_to: filter.issuedTo || undefined,
      search: filter.search?.trim() || undefined,
      customer_id: filter.customerId || undefined,
      order_id: filter.orderId || undefined,
    }).pipe(map((res) => res.body));
  }

  get(invoiceId: string): Observable<InvoiceResponse> {
    return getInvoiceApiV1InvoicesInvoiceIdGet(this.http, this.config.rootUrl, {
      invoice_id: invoiceId,
    }).pipe(map((res) => res.body));
  }

  recordPayment(invoiceId: string, input: RecordPaymentInput): Observable<InvoiceResponse> {
    return recordPaymentApiV1InvoicesInvoiceIdPaymentsPost(this.http, this.config.rootUrl, {
      invoice_id: invoiceId,
      body: {
        method: input.method,
        amount: input.amount,
        reference: input.reference?.trim() || null,
      },
    }).pipe(map((res) => res.body));
  }

  /** Delivered (or charged-cancellation) orders with no invoice — usually
   * held because GST was not configured when they were delivered. */
  listUninvoicedOrders(): Observable<UninvoicedOrderResponse[]> {
    return listUninvoicedOrdersApiV1InvoicesUninvoicedOrdersGet(
      this.http,
      this.config.rootUrl,
    ).pipe(map((res) => res.body));
  }

  issueForOrder(orderId: string): Observable<InvoiceResponse> {
    return issueInvoiceApiV1InvoicesPost(this.http, this.config.rootUrl, {
      body: { order_id: orderId },
    }).pipe(map((res) => res.body));
  }

  /** E-mails the invoice to the customer and pushes it to their app. */
  sendToCustomer(invoiceId: string): Observable<InvoiceResponse> {
    return sendInvoiceApiV1InvoicesInvoiceIdSendPost(this.http, this.config.rootUrl, {
      invoice_id: invoiceId,
    }).pipe(map((res) => res.body));
  }

  listCreditNotes(invoiceId: string): Observable<CreditNoteResponse[]> {
    return listCreditNotesApiV1InvoicesInvoiceIdCreditNotesGet(this.http, this.config.rootUrl, {
      invoice_id: invoiceId,
    }).pipe(map((res) => res.body));
  }

  requestRefund(invoiceId: string, amount: string, reason: string): Observable<CreditNoteResponse> {
    return requestRefundApiV1InvoicesInvoiceIdRefundsPost(this.http, this.config.rootUrl, {
      invoice_id: invoiceId,
      body: { amount, reason },
    }).pipe(map((res) => res.body));
  }

  approveRefund(invoiceId: string, creditNoteId: string): Observable<CreditNoteResponse> {
    return approveRefundApiV1InvoicesInvoiceIdRefundsCreditNoteIdApprovePost(
      this.http,
      this.config.rootUrl,
      { invoice_id: invoiceId, credit_note_id: creditNoteId },
    ).pipe(map((res) => res.body));
  }

  /** A Razorpay link for what is still owed on the order. Fails with 503
   * when online payments are not configured for this environment. */
  createPaymentLink(orderId: string): Observable<OnlinePaymentResponse> {
    return createPaymentLinkApiV1OrdersOrderIdPaymentLinksPost(this.http, this.config.rootUrl, {
      order_id: orderId,
    }).pipe(map((res) => res.body));
  }
}
