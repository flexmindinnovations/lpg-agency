import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getPaymentProfileApiV1PaymentProfileGet } from './generated/fn/payment-profile/get-payment-profile-api-v-1-payment-profile-get';
import { setPaymentProfileApiV1PaymentProfilePut } from './generated/fn/payment-profile/set-payment-profile-api-v-1-payment-profile-put';
import { getUpiQrApiV1PaymentsUpiQrGet } from './generated/fn/payment-profile/get-upi-qr-api-v-1-payments-upi-qr-get';
import type { PaymentProfileResponse } from './generated/models/payment-profile-response';
import type { SetPaymentProfileRequest } from './generated/models/set-payment-profile-request';
import type { UpiQrResponse } from './generated/models/upi-qr-response';

/** The agency's bank and UPI details, and the UPI pay QR (ADR-066). */
@Injectable({ providedIn: 'root' })
export class PaymentProfileService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  get(): Observable<PaymentProfileResponse> {
    return getPaymentProfileApiV1PaymentProfileGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  save(body: SetPaymentProfileRequest): Observable<PaymentProfileResponse> {
    return setPaymentProfileApiV1PaymentProfilePut(this.http, this.config.rootUrl, { body }).pipe(
      map((res) => res.body),
    );
  }

  /** UPI link and QR image for what is still owed on an order or invoice.
   * Fails with 409 when no UPI ID is set up or nothing is due. */
  upiQr(target: { orderId?: string; invoiceId?: string }): Observable<UpiQrResponse> {
    return getUpiQrApiV1PaymentsUpiQrGet(this.http, this.config.rootUrl, {
      order_id: target.orderId ?? null,
      invoice_id: target.invoiceId ?? null,
    }).pipe(map((res) => res.body));
  }
}
