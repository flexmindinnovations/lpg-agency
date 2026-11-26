import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { classifyCylinderTypeForGstApiV1AdminCylinderTypesCylinderTypeIdGstPatch } from './generated/fn/administration/classify-cylinder-type-for-gst-api-v-1-admin-cylinder-types-cylinder-type-id-gst-patch';
import { createCylinderTypeApiV1AdminCylinderTypesPost } from './generated/fn/administration/create-cylinder-type-api-v-1-admin-cylinder-types-post';
import { deleteCylinderTypeApiV1AdminCylinderTypesCylinderTypeIdDelete } from './generated/fn/administration/delete-cylinder-type-api-v-1-admin-cylinder-types-cylinder-type-id-delete';
import { getCylinderTypeUsageApiV1AdminCylinderTypesCylinderTypeIdUsageGet } from './generated/fn/administration/get-cylinder-type-usage-api-v-1-admin-cylinder-types-cylinder-type-id-usage-get';
import { listCylinderSizesApiV1AdminCylinderSizesGet } from './generated/fn/administration/list-cylinder-sizes-api-v-1-admin-cylinder-sizes-get';
import { listCylinderTypesApiV1AdminCylinderTypesGet } from './generated/fn/administration/list-cylinder-types-api-v-1-admin-cylinder-types-get';
import { setCylinderTypeActiveApiV1AdminCylinderTypesCylinderTypeIdActivePatch } from './generated/fn/administration/set-cylinder-type-active-api-v-1-admin-cylinder-types-cylinder-type-id-active-patch';
import { updateCylinderTypeApiV1AdminCylinderTypesCylinderTypeIdPatch } from './generated/fn/administration/update-cylinder-type-api-v-1-admin-cylinder-types-cylinder-type-id-patch';
import type { CylinderSizeResponse } from './generated/models/cylinder-size-response';
import type { CylinderTypeResponse } from './generated/models/cylinder-type-response';
import type { CylinderTypeUsageResponse } from './generated/models/cylinder-type-usage-response';

export interface CylinderTypeGst {
  readonly hsnCode: string;
  readonly gstRatePercent: number;
}

/** Thin wrapper over the generated `/admin/cylinder-types` client functions. */
@Injectable({ providedIn: 'root' })
export class AdminCylinderTypeService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listCylinderTypes(): Observable<CylinderTypeResponse[]> {
    return listCylinderTypesApiV1AdminCylinderTypesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  /** The standard sizes a cylinder type is picked from (ADR-079). */
  listCylinderSizes(): Observable<CylinderSizeResponse[]> {
    return listCylinderSizesApiV1AdminCylinderSizesGet(this.http, this.config.rootUrl).pipe(
      map((response) => response.body),
    );
  }

  createCylinderType(sizeCode: string, gst?: CylinderTypeGst): Observable<CylinderTypeResponse> {
    return createCylinderTypeApiV1AdminCylinderTypesPost(this.http, this.config.rootUrl, {
      body: {
        size_code: sizeCode,
        hsn_code: gst?.hsnCode ?? null,
        gst_rate_percent: gst?.gstRatePercent ?? null,
      },
    }).pipe(map((response) => response.body));
  }

  /** Anything left out of `changes` stays as it is. */
  updateCylinderType(
    cylinderTypeId: string,
    changes: { sizeCode?: string; gst?: CylinderTypeGst },
  ): Observable<CylinderTypeResponse> {
    return updateCylinderTypeApiV1AdminCylinderTypesCylinderTypeIdPatch(
      this.http,
      this.config.rootUrl,
      {
        cylinder_type_id: cylinderTypeId,
        body: {
          size_code: changes.sizeCode ?? null,
          hsn_code: changes.gst?.hsnCode ?? null,
          gst_rate_percent: changes.gst?.gstRatePercent ?? null,
        },
      },
    ).pipe(map((response) => response.body));
  }

  /** What refers to a cylinder type, which limits how it can change. */
  getUsage(cylinderTypeId: string): Observable<CylinderTypeUsageResponse> {
    return getCylinderTypeUsageApiV1AdminCylinderTypesCylinderTypeIdUsageGet(
      this.http,
      this.config.rootUrl,
      { cylinder_type_id: cylinderTypeId },
    ).pipe(map((response) => response.body));
  }

  deleteCylinderType(cylinderTypeId: string): Observable<void> {
    return deleteCylinderTypeApiV1AdminCylinderTypesCylinderTypeIdDelete(
      this.http,
      this.config.rootUrl,
      { cylinder_type_id: cylinderTypeId },
    ).pipe(map(() => undefined));
  }

  /** Set the HSN code and GST rate invoices use for this cylinder type
   * (DA-06). Until it is set, deliveries of it are held, not invoiced. */
  classifyForGst(
    cylinderTypeId: string,
    hsnCode: string,
    gstRatePercent: number,
  ): Observable<CylinderTypeResponse> {
    return classifyCylinderTypeForGstApiV1AdminCylinderTypesCylinderTypeIdGstPatch(
      this.http,
      this.config.rootUrl,
      {
        cylinder_type_id: cylinderTypeId,
        body: { hsn_code: hsnCode, gst_rate_percent: gstRatePercent },
      },
    ).pipe(map((response) => response.body));
  }

  setActive(cylinderTypeId: string, isActive: boolean): Observable<void> {
    return setCylinderTypeActiveApiV1AdminCylinderTypesCylinderTypeIdActivePatch(
      this.http,
      this.config.rootUrl,
      { cylinder_type_id: cylinderTypeId, body: { is_active: isActive } },
    ).pipe(map(() => undefined));
  }
}
