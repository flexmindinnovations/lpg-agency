import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

import { adjustInventoryApiV1InventoryLocationsLocationTypeLocationRefIdAdjustmentsPost } from './generated/fn/inventory/adjust-inventory-api-v-1-inventory-locations-location-type-location-ref-id-adjustments-post';
import { approveReconciliationRecordApiV1ReconciliationRecordsRecordIdApprovePost } from './generated/fn/inventory/approve-reconciliation-record-api-v-1-reconciliation-records-record-id-approve-post';
import { changeCylinderStatusApiV1InventoryLocationsLocationTypeLocationRefIdStatusChangesPost } from './generated/fn/inventory/change-cylinder-status-api-v-1-inventory-locations-location-type-location-ref-id-status-changes-post';
import { createLoadTransferApiV1InventoryLoadTransfersPost } from './generated/fn/inventory/create-load-transfer-api-v-1-inventory-load-transfers-post';
import { createReconciliationRecordApiV1InventoryLocationsLocationTypeLocationRefIdReconciliationRecordsPost } from './generated/fn/inventory/create-reconciliation-record-api-v-1-inventory-locations-location-type-location-ref-id-reconciliation-records-post';
import { getInventoryBalanceApiV1InventoryLocationsLocationTypeLocationRefIdBalanceGet } from './generated/fn/inventory/get-inventory-balance-api-v-1-inventory-locations-location-type-location-ref-id-balance-get';
import { listInventoryTransactionsApiV1InventoryLocationsLocationTypeLocationRefIdTransactionsGet } from './generated/fn/inventory/list-inventory-transactions-api-v-1-inventory-locations-location-type-location-ref-id-transactions-get';
import { recordCollectionApiV1VehiclesVehicleIdCollectionsPost } from './generated/fn/inventory/record-collection-api-v-1-vehicles-vehicle-id-collections-post';
import { recordDeliveryApiV1VehiclesVehicleIdDeliveriesPost } from './generated/fn/inventory/record-delivery-api-v-1-vehicles-vehicle-id-deliveries-post';
import { recordGoodsReceiptApiV1WarehousesWarehouseIdGoodsReceiptNotesPost } from './generated/fn/inventory/record-goods-receipt-api-v-1-warehouses-warehouse-id-goods-receipt-notes-post';

import type { AdjustInventoryRequest } from './generated/models/adjust-inventory-request';
import type { ChangeCylinderStatusRequest } from './generated/models/change-cylinder-status-request';
import type { GoodsReceiptRequest } from './generated/models/goods-receipt-request';
import type { GoodsReceiptResponse } from './generated/models/goods-receipt-response';
import type { InventoryBalanceResponse } from './generated/models/inventory-balance-response';
import type { InventoryTransactionPageResponse } from './generated/models/inventory-transaction-page-response';
import type { LoadTransferRequest } from './generated/models/load-transfer-request';
import type { LoadTransferResponse } from './generated/models/load-transfer-response';
import type { ReconciliationRecordCreateRequest } from './generated/models/reconciliation-record-create-request';
import type { ReconciliationRecordResponse } from './generated/models/reconciliation-record-response';
import type { RecordCollectionRequest } from './generated/models/record-collection-request';
import type { RecordDeliveryRequest } from './generated/models/record-delivery-request';

export type InventoryLocationType = 'warehouse' | 'vehicle';

@Injectable({ providedIn: 'root' })
export class InventoryService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  // ---------------------------------------------------------------------------
  // Balance / transaction history
  // ---------------------------------------------------------------------------

  getBalance(
    locationType: InventoryLocationType,
    locationRefId: string,
  ): Observable<InventoryBalanceResponse> {
    return getInventoryBalanceApiV1InventoryLocationsLocationTypeLocationRefIdBalanceGet(
      this.http,
      this.config.rootUrl,
      { location_type: locationType, location_ref_id: locationRefId },
    ).pipe(map((res) => res.body));
  }

  listTransactions(
    locationType: InventoryLocationType,
    locationRefId: string,
    cursor?: string,
    limit = 50,
  ): Observable<InventoryTransactionPageResponse> {
    return listInventoryTransactionsApiV1InventoryLocationsLocationTypeLocationRefIdTransactionsGet(
      this.http,
      this.config.rootUrl,
      { location_type: locationType, location_ref_id: locationRefId, cursor, limit },
    ).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Goods receipt / load transfer
  // ---------------------------------------------------------------------------

  recordGoodsReceipt(
    warehouseId: string,
    request: GoodsReceiptRequest,
  ): Observable<GoodsReceiptResponse> {
    return recordGoodsReceiptApiV1WarehousesWarehouseIdGoodsReceiptNotesPost(
      this.http,
      this.config.rootUrl,
      { warehouse_id: warehouseId, body: request },
    ).pipe(map((res) => res.body));
  }

  createLoadTransfer(request: LoadTransferRequest): Observable<LoadTransferResponse> {
    return createLoadTransferApiV1InventoryLoadTransfersPost(this.http, this.config.rootUrl, {
      body: request,
    }).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Delivery / collection (vehicle-only)
  // ---------------------------------------------------------------------------

  recordDelivery(
    vehicleId: string,
    request: RecordDeliveryRequest,
  ): Observable<InventoryBalanceResponse> {
    return recordDeliveryApiV1VehiclesVehicleIdDeliveriesPost(this.http, this.config.rootUrl, {
      vehicle_id: vehicleId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  recordCollection(
    vehicleId: string,
    request: RecordCollectionRequest,
  ): Observable<InventoryBalanceResponse> {
    return recordCollectionApiV1VehiclesVehicleIdCollectionsPost(this.http, this.config.rootUrl, {
      vehicle_id: vehicleId,
      body: request,
    }).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Status change / adjustment
  // ---------------------------------------------------------------------------

  changeCylinderStatus(
    locationType: InventoryLocationType,
    locationRefId: string,
    request: ChangeCylinderStatusRequest,
  ): Observable<InventoryBalanceResponse> {
    return changeCylinderStatusApiV1InventoryLocationsLocationTypeLocationRefIdStatusChangesPost(
      this.http,
      this.config.rootUrl,
      { location_type: locationType, location_ref_id: locationRefId, body: request },
    ).pipe(map((res) => res.body));
  }

  adjustInventory(
    locationType: InventoryLocationType,
    locationRefId: string,
    request: AdjustInventoryRequest,
  ): Observable<InventoryBalanceResponse> {
    return adjustInventoryApiV1InventoryLocationsLocationTypeLocationRefIdAdjustmentsPost(
      this.http,
      this.config.rootUrl,
      { location_type: locationType, location_ref_id: locationRefId, body: request },
    ).pipe(map((res) => res.body));
  }

  // ---------------------------------------------------------------------------
  // Reconciliation
  // ---------------------------------------------------------------------------

  createReconciliationRecord(
    locationType: InventoryLocationType,
    locationRefId: string,
    request: ReconciliationRecordCreateRequest,
  ): Observable<ReconciliationRecordResponse> {
    return createReconciliationRecordApiV1InventoryLocationsLocationTypeLocationRefIdReconciliationRecordsPost(
      this.http,
      this.config.rootUrl,
      { location_type: locationType, location_ref_id: locationRefId, body: request },
    ).pipe(map((res) => res.body));
  }

  approveReconciliationRecord(recordId: string): Observable<ReconciliationRecordResponse> {
    return approveReconciliationRecordApiV1ReconciliationRecordsRecordIdApprovePost(
      this.http,
      this.config.rootUrl,
      { record_id: recordId },
    ).pipe(map((res) => res.body));
  }
}
