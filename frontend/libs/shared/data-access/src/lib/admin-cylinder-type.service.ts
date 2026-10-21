import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { adjustCylinderTypeWeightApiV1AdminCylinderTypesCylinderTypeIdWeightPatch } from './generated/fn/administration/adjust-cylinder-type-weight-api-v-1-admin-cylinder-types-cylinder-type-id-weight-patch';
import { classifyCylinderTypeForGstApiV1AdminCylinderTypesCylinderTypeIdGstPatch } from './generated/fn/administration/classify-cylinder-type-for-gst-api-v-1-admin-cylinder-types-cylinder-type-id-gst-patch';
import { createCylinderTypeApiV1AdminCylinderTypesPost } from './generated/fn/administration/create-cylinder-type-api-v-1-admin-cylinder-types-post';
import { listCylinderTypesApiV1AdminCylinderTypesGet } from './generated/fn/administration/list-cylinder-types-api-v-1-admin-cylinder-types-get';
import { renameCylinderTypeApiV1AdminCylinderTypesCylinderTypeIdRenamePatch } from './generated/fn/administration/rename-cylinder-type-api-v-1-admin-cylinder-types-cylinder-type-id-rename-patch';
import { setCylinderTypeActiveApiV1AdminCylinderTypesCylinderTypeIdActivePatch } from './generated/fn/administration/set-cylinder-type-active-api-v-1-admin-cylinder-types-cylinder-type-id-active-patch';
import type { CylinderTypeResponse } from './generated/models/cylinder-type-response';

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

  createCylinderType(
    name: string,
    weightKg: number,
    gst?: { hsnCode: string; gstRatePercent: number },
  ): Observable<CylinderTypeResponse> {
    return createCylinderTypeApiV1AdminCylinderTypesPost(this.http, this.config.rootUrl, {
      body: {
        name,
        weight_kg: weightKg,
        hsn_code: gst?.hsnCode ?? null,
        gst_rate_percent: gst?.gstRatePercent ?? null,
      },
    }).pipe(map((response) => response.body));
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

  renameCylinderType(cylinderTypeId: string, name: string): Observable<void> {
    return renameCylinderTypeApiV1AdminCylinderTypesCylinderTypeIdRenamePatch(
      this.http,
      this.config.rootUrl,
      { cylinder_type_id: cylinderTypeId, body: { name } },
    ).pipe(map(() => undefined));
  }

  adjustWeight(cylinderTypeId: string, weightKg: number): Observable<void> {
    return adjustCylinderTypeWeightApiV1AdminCylinderTypesCylinderTypeIdWeightPatch(
      this.http,
      this.config.rootUrl,
      { cylinder_type_id: cylinderTypeId, body: { weight_kg: weightKg } },
    ).pipe(map(() => undefined));
  }

  setActive(cylinderTypeId: string, isActive: boolean): Observable<void> {
    return setCylinderTypeActiveApiV1AdminCylinderTypesCylinderTypeIdActivePatch(
      this.http,
      this.config.rootUrl,
      { cylinder_type_id: cylinderTypeId, body: { is_active: isActive } },
    ).pipe(map(() => undefined));
  }
}
