import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getPaymentGatewaySettingsApiV1PaymentGatewayGet } from './generated/fn/online-payments/get-payment-gateway-settings-api-v-1-payment-gateway-get';
import { setPaymentGatewayApiV1PaymentGatewayPut } from './generated/fn/online-payments/set-payment-gateway-api-v-1-payment-gateway-put';
import { removePaymentGatewayApiV1PaymentGatewayDelete } from './generated/fn/online-payments/remove-payment-gateway-api-v-1-payment-gateway-delete';
import { rotatePaymentWebhookTokenApiV1PaymentGatewayRotateWebhookTokenPost } from './generated/fn/online-payments/rotate-payment-webhook-token-api-v-1-payment-gateway-rotate-webhook-token-post';
import { testPaymentGatewayApiV1PaymentGatewayTestPost } from './generated/fn/online-payments/test-payment-gateway-api-v-1-payment-gateway-test-post';
import type { PaymentGatewaySettingsResponse } from './generated/models/payment-gateway-settings-response';
import type { PaymentGatewayTestResponse } from './generated/models/payment-gateway-test-response';
import type { SetPaymentGatewayRequest } from './generated/models/set-payment-gateway-request';

/** The agency's own Razorpay account (ADR-067). Secrets are write-only: the
 * server never sends them back, only a masked key id and "is set" flags. */
@Injectable({ providedIn: 'root' })
export class PaymentGatewayService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  get(): Observable<PaymentGatewaySettingsResponse> {
    return getPaymentGatewaySettingsApiV1PaymentGatewayGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  save(body: SetPaymentGatewayRequest): Observable<PaymentGatewaySettingsResponse> {
    return setPaymentGatewayApiV1PaymentGatewayPut(this.http, this.config.rootUrl, { body }).pipe(
      map((res) => res.body),
    );
  }

  remove(): Observable<void> {
    return removePaymentGatewayApiV1PaymentGatewayDelete(this.http, this.config.rootUrl).pipe(
      map(() => undefined),
    );
  }

  /** Issues a new webhook URL; the old one stops working at once. */
  rotateWebhookUrl(): Observable<PaymentGatewaySettingsResponse> {
    return rotatePaymentWebhookTokenApiV1PaymentGatewayRotateWebhookTokenPost(
      this.http,
      this.config.rootUrl,
    ).pipe(map((res) => res.body));
  }

  /** One authenticated call to Razorpay with the saved key. */
  test(): Observable<PaymentGatewayTestResponse> {
    return testPaymentGatewayApiV1PaymentGatewayTestPost(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }
}
