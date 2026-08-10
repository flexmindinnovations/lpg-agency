import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getEffectivePriceApiV1AdminPriceListEffectiveGet } from './generated/fn/administration/get-effective-price-api-v-1-admin-price-list-effective-get';
import { listPricesApiV1AdminPriceListGet } from './generated/fn/administration/list-prices-api-v-1-admin-price-list-get';
import { setPriceApiV1AdminPriceListPost } from './generated/fn/administration/set-price-api-v-1-admin-price-list-post';
import type { PriceListEntryResponse } from './generated/models/price-list-entry-response';

/** Thin wrapper over the generated `/admin/price-list` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminPriceListService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listPrices(): Observable<PriceListEntryResponse[]> {
    return listPricesApiV1AdminPriceListGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  setPrice(
    cylinderTypeId: string,
    customerType: string,
    price: number,
    branchId: string | null = null,
    effectiveFrom: string | null = null,
  ): Observable<PriceListEntryResponse> {
    return setPriceApiV1AdminPriceListPost(this.http, this.config.rootUrl, {
      body: {
        cylinder_type_id: cylinderTypeId,
        customer_type: customerType,
        price,
        branch_id: branchId,
        effective_from: effectiveFrom,
      },
    }).pipe(map((response) => response.body));
  }

  getEffectivePrice(
    cylinderTypeId: string,
    customerType: string,
    branchId: string | null = null,
  ): Observable<PriceListEntryResponse | null> {
    return getEffectivePriceApiV1AdminPriceListEffectiveGet(this.http, this.config.rootUrl, {
      cylinder_type_id: cylinderTypeId,
      customer_type: customerType,
      branch_id: branchId,
    }).pipe(map((response) => response.body));
  }
}
