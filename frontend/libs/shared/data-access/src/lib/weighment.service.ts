import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listScalesApiV1ScalesGet } from './generated/fn/compliance-weighment/list-scales-api-v-1-scales-get';
import { registerScaleApiV1ScalesPost } from './generated/fn/compliance-weighment/register-scale-api-v-1-scales-post';
import { replaceScaleCertificateApiV1ScalesScaleIdCertificatePut } from './generated/fn/compliance-weighment/replace-scale-certificate-api-v-1-scales-scale-id-certificate-put';
import { setScaleStatusApiV1ScalesScaleIdStatusPut } from './generated/fn/compliance-weighment/set-scale-status-api-v-1-scales-scale-id-status-put';
import { recordGoodsReceiptWeighmentApiV1GoodsReceiptNotesGrnIdWeighmentPost } from './generated/fn/compliance-weighment/record-goods-receipt-weighment-api-v-1-goods-receipt-notes-grn-id-weighment-post';
import { listGoodsReceiptWeighmentsApiV1GoodsReceiptNotesGrnIdWeighmentGet } from './generated/fn/compliance-weighment/list-goods-receipt-weighments-api-v-1-goods-receipt-notes-grn-id-weighment-get';
import { recordRouteLoadOutWeighmentApiV1RoutesRouteIdWeighmentPost } from './generated/fn/compliance-weighment/record-route-load-out-weighment-api-v-1-routes-route-id-weighment-post';
import { listRouteWeighmentsApiV1RoutesRouteIdWeighmentGet } from './generated/fn/compliance-weighment/list-route-weighments-api-v-1-routes-route-id-weighment-get';
import type { RegisterScaleRequest } from './generated/models/register-scale-request';
import type { ReplaceScaleCertificateRequest } from './generated/models/replace-scale-certificate-request';
import type { ScaleListResponse } from './generated/models/scale-list-response';
import type { ScaleResponse } from './generated/models/scale-response';
import type { RecordWeighmentRequest } from './generated/models/record-weighment-request';
import type { WeighmentRecordListResponse } from './generated/models/weighment-record-list-response';
import type { WeighmentRecordResponse } from './generated/models/weighment-record-response';

export interface ScaleListFilter {
  status?: string;
  expiry?: 'expiring' | 'expired';
  skip?: number;
  limit?: number;
}

/**
 * Thin wrapper over the generated `/scales` + weighment-record client
 * functions — same pattern as `DocumentService`. Feeds the Scales registry
 * page and the weighment-capture mini-forms on the GRN and route load-out
 * screens (Weighment Parts 1–3).
 */
@Injectable({ providedIn: 'root' })
export class WeighmentService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  registerScale(body: RegisterScaleRequest): Observable<ScaleResponse> {
    return registerScaleApiV1ScalesPost(this.http, this.config.rootUrl, { body }).pipe(
      map((res) => res.body),
    );
  }

  listScales(filter: ScaleListFilter = {}): Observable<ScaleListResponse> {
    return listScalesApiV1ScalesGet(this.http, this.config.rootUrl, {
      status: filter.status,
      expiry: filter.expiry,
      skip: filter.skip,
      limit: filter.limit,
    }).pipe(map((res) => res.body));
  }

  replaceScaleCertificate(
    scaleId: string,
    body: ReplaceScaleCertificateRequest,
  ): Observable<ScaleResponse> {
    return replaceScaleCertificateApiV1ScalesScaleIdCertificatePut(this.http, this.config.rootUrl, {
      scale_id: scaleId,
      body,
    }).pipe(map((res) => res.body));
  }

  setScaleStatus(scaleId: string, status: string): Observable<ScaleResponse> {
    return setScaleStatusApiV1ScalesScaleIdStatusPut(this.http, this.config.rootUrl, {
      scale_id: scaleId,
      body: { status },
    }).pipe(map((res) => res.body));
  }

  /** MDG 2022 cl. 1.2(iv) — 10% goods-receipt sample. Non-blocking. */
  recordGoodsReceiptWeighment(
    grnId: string,
    body: RecordWeighmentRequest,
  ): Observable<WeighmentRecordResponse> {
    return recordGoodsReceiptWeighmentApiV1GoodsReceiptNotesGrnIdWeighmentPost(
      this.http,
      this.config.rootUrl,
      { grn_id: grnId, body },
    ).pipe(map((res) => res.body));
  }

  listGoodsReceiptWeighments(grnId: string): Observable<WeighmentRecordListResponse> {
    return listGoodsReceiptWeighmentsApiV1GoodsReceiptNotesGrnIdWeighmentGet(
      this.http,
      this.config.rootUrl,
      { grn_id: grnId },
    ).pipe(map((res) => res.body));
  }

  /** MDG 2022 cl. 1.4(c)(d) — 100% load-out check. Feeds the tenant-opt-in
   * dispatch gate on `POST /routes/{id}/load`. */
  recordRouteLoadOutWeighment(
    routeId: string,
    body: RecordWeighmentRequest,
  ): Observable<WeighmentRecordResponse> {
    return recordRouteLoadOutWeighmentApiV1RoutesRouteIdWeighmentPost(
      this.http,
      this.config.rootUrl,
      { route_id: routeId, body },
    ).pipe(map((res) => res.body));
  }

  listRouteWeighments(routeId: string): Observable<WeighmentRecordListResponse> {
    return listRouteWeighmentsApiV1RoutesRouteIdWeighmentGet(this.http, this.config.rootUrl, {
      route_id: routeId,
    }).pipe(map((res) => res.body));
  }
}
