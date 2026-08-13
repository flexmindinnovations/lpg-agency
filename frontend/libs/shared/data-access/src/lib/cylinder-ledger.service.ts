import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getLedgerApiV1CustomersCustomerIdLedgerGet } from './generated/fn/cylinder-ledger/get-ledger-api-v-1-customers-customer-id-ledger-get';
import { adjustBalanceApiV1CustomersCustomerIdLedgerAdjustPost } from './generated/fn/cylinder-ledger/adjust-balance-api-v-1-customers-customer-id-ledger-adjust-post';
import type { CylinderLedgerResponse } from './generated/models/cylinder-ledger-response';
import type { AdjustLedgerBalanceRequest } from './generated/models/adjust-ledger-balance-request';

@Injectable({ providedIn: 'root' })
export class CylinderLedgerService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  getLedger(customerId: string): Observable<CylinderLedgerResponse> {
    return getLedgerApiV1CustomersCustomerIdLedgerGet(this.http, this.config.rootUrl, {
      customer_id: customerId,
    }).pipe(map((res) => res.body));
  }

  adjustBalance(customerId: string, request: AdjustLedgerBalanceRequest): Observable<CylinderLedgerResponse> {
    return adjustBalanceApiV1CustomersCustomerIdLedgerAdjustPost(this.http, this.config.rootUrl, {
      customer_id: customerId,
      body: request,
    }).pipe(map((res) => res.body));
  }
}
