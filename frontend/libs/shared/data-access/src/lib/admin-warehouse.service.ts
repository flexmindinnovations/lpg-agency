import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { createWarehouseApiV1AdminWarehousesPost } from './generated/fn/administration/create-warehouse-api-v-1-admin-warehouses-post';
import { listWarehousesApiV1AdminWarehousesGet } from './generated/fn/administration/list-warehouses-api-v-1-admin-warehouses-get';
import { relocateWarehouseApiV1AdminWarehousesWarehouseIdRelocatePatch } from './generated/fn/administration/relocate-warehouse-api-v-1-admin-warehouses-warehouse-id-relocate-patch';
import { renameWarehouseApiV1AdminWarehousesWarehouseIdRenamePatch } from './generated/fn/administration/rename-warehouse-api-v-1-admin-warehouses-warehouse-id-rename-patch';
import type { WarehouseResponse } from './generated/models/warehouse-response';

/** Thin wrapper over the generated `/admin/warehouses` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminWarehouseService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listWarehouses(): Observable<WarehouseResponse[]> {
    return listWarehousesApiV1AdminWarehousesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  createWarehouse(
    branchId: string,
    name: string,
    addressLine: string,
  ): Observable<WarehouseResponse> {
    return createWarehouseApiV1AdminWarehousesPost(this.http, this.config.rootUrl, {
      body: { branch_id: branchId, name, address_line: addressLine },
    }).pipe(map((response) => response.body));
  }

  renameWarehouse(warehouseId: string, name: string): Observable<void> {
    return renameWarehouseApiV1AdminWarehousesWarehouseIdRenamePatch(
      this.http,
      this.config.rootUrl,
      { warehouse_id: warehouseId, body: { name } },
    ).pipe(map(() => undefined));
  }

  relocateWarehouse(warehouseId: string, addressLine: string): Observable<void> {
    return relocateWarehouseApiV1AdminWarehousesWarehouseIdRelocatePatch(
      this.http,
      this.config.rootUrl,
      { warehouse_id: warehouseId, body: { address_line: addressLine } },
    ).pipe(map(() => undefined));
  }
}
