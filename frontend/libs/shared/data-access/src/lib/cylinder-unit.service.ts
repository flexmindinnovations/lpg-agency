import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { registerCylinderUnitApiV1CylinderUnitsPost } from './generated/fn/compliance-cylinder-identity/register-cylinder-unit-api-v-1-cylinder-units-post';
import { listCylinderUnitsApiV1CylinderUnitsGet } from './generated/fn/compliance-cylinder-identity/list-cylinder-units-api-v-1-cylinder-units-get';
import { getCylinderUnitApiV1CylinderUnitsCylinderUnitIdGet } from './generated/fn/compliance-cylinder-identity/get-cylinder-unit-api-v-1-cylinder-units-cylinder-unit-id-get';
import { suggestCylinderTestDueDateApiV1CylinderUnitsSuggestTestDueDateGet } from './generated/fn/compliance-cylinder-identity/suggest-cylinder-test-due-date-api-v-1-cylinder-units-suggest-test-due-date-get';
import { recordCylinderStatutoryTestApiV1CylinderUnitsCylinderUnitIdTestPost } from './generated/fn/compliance-cylinder-identity/record-cylinder-statutory-test-api-v-1-cylinder-units-cylinder-unit-id-test-post';
import { moveCylinderCustodyApiV1CylinderUnitsCylinderUnitIdCustodyPost } from './generated/fn/compliance-cylinder-identity/move-cylinder-custody-api-v-1-cylinder-units-cylinder-unit-id-custody-post';
import { changeCylinderConditionStatusApiV1CylinderUnitsCylinderUnitIdConditionPost } from './generated/fn/compliance-cylinder-identity/change-cylinder-condition-status-api-v-1-cylinder-units-cylinder-unit-id-condition-post';
import { receiveCylinderUnitApiV1CylinderUnitsCylinderUnitIdReceivePost } from './generated/fn/compliance-cylinder-identity/receive-cylinder-unit-api-v-1-cylinder-units-cylinder-unit-id-receive-post';
import { retireCylinderUnitApiV1CylinderUnitsCylinderUnitIdRetirePost } from './generated/fn/compliance-cylinder-identity/retire-cylinder-unit-api-v-1-cylinder-units-cylinder-unit-id-retire-post';
import type { RegisterCylinderUnitRequest } from './generated/models/register-cylinder-unit-request';
import type { RecordCylinderStatutoryTestRequest } from './generated/models/record-cylinder-statutory-test-request';
import type { MoveCylinderCustodyRequest } from './generated/models/move-cylinder-custody-request';
import type { ChangeCylinderConditionStatusRequest } from './generated/models/change-cylinder-condition-status-request';
import type { CylinderUnitResponse } from './generated/models/cylinder-unit-response';
import type { CylinderUnitListResponse } from './generated/models/cylinder-unit-list-response';
import type { SuggestCylinderTestDueDateResponse } from './generated/models/suggest-cylinder-test-due-date-response';

export interface CylinderUnitListFilter {
  dueStatus?: 'due_soon' | 'overdue' | null;
  cylinderTypeId?: string | null;
  custodyType?: string | null;
  skip?: number;
  limit?: number;
}

/**
 * Thin wrapper over the generated `/cylinder-units` client functions —
 * same pattern as `WeighmentService`. Feeds the Cylinder Units registry
 * page (Cylinder Identity, Phase 20 subsystem 3).
 */
@Injectable({ providedIn: 'root' })
export class CylinderUnitService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  registerCylinderUnit(body: RegisterCylinderUnitRequest): Observable<CylinderUnitResponse> {
    return registerCylinderUnitApiV1CylinderUnitsPost(this.http, this.config.rootUrl, {
      body,
    }).pipe(map((res) => res.body));
  }

  listCylinderUnits(filter: CylinderUnitListFilter = {}): Observable<CylinderUnitListResponse> {
    return listCylinderUnitsApiV1CylinderUnitsGet(this.http, this.config.rootUrl, {
      due_status: filter.dueStatus,
      cylinder_type_id: filter.cylinderTypeId,
      custody_type: filter.custodyType,
      skip: filter.skip,
      limit: filter.limit,
    }).pipe(map((res) => res.body));
  }

  getCylinderUnit(cylinderUnitId: string): Observable<CylinderUnitResponse> {
    return getCylinderUnitApiV1CylinderUnitsCylinderUnitIdGet(this.http, this.config.rootUrl, {
      cylinder_unit_id: cylinderUnitId,
    }).pipe(map((res) => res.body));
  }

  /** `suggested_due_date` is `null` when the tenant has no
   * `cylinder_statutory_test_interval_months` configured — a convenience
   * only, never a guessed interval. */
  suggestTestDueDate(testedAt: string): Observable<SuggestCylinderTestDueDateResponse> {
    return suggestCylinderTestDueDateApiV1CylinderUnitsSuggestTestDueDateGet(
      this.http,
      this.config.rootUrl,
      { tested_at: testedAt },
    ).pipe(map((res) => res.body));
  }

  recordStatutoryTest(
    cylinderUnitId: string,
    body: RecordCylinderStatutoryTestRequest,
  ): Observable<CylinderUnitResponse> {
    return recordCylinderStatutoryTestApiV1CylinderUnitsCylinderUnitIdTestPost(
      this.http,
      this.config.rootUrl,
      { cylinder_unit_id: cylinderUnitId, body },
    ).pipe(map((res) => res.body));
  }

  moveCustody(
    cylinderUnitId: string,
    body: MoveCylinderCustodyRequest,
  ): Observable<CylinderUnitResponse> {
    return moveCylinderCustodyApiV1CylinderUnitsCylinderUnitIdCustodyPost(
      this.http,
      this.config.rootUrl,
      { cylinder_unit_id: cylinderUnitId, body },
    ).pipe(map((res) => res.body));
  }

  changeConditionStatus(
    cylinderUnitId: string,
    body: ChangeCylinderConditionStatusRequest,
  ): Observable<CylinderUnitResponse> {
    return changeCylinderConditionStatusApiV1CylinderUnitsCylinderUnitIdConditionPost(
      this.http,
      this.config.rootUrl,
      { cylinder_unit_id: cylinderUnitId, body },
    ).pipe(map((res) => res.body));
  }

  /** Rule 26, Gas Cylinders Rules 2016 — 409 if this unit is due for
   * statutory retest. */
  receiveCylinderUnit(
    cylinderUnitId: string,
    warehouseId: string,
  ): Observable<CylinderUnitResponse> {
    return receiveCylinderUnitApiV1CylinderUnitsCylinderUnitIdReceivePost(
      this.http,
      this.config.rootUrl,
      { cylinder_unit_id: cylinderUnitId, body: { warehouse_id: warehouseId } },
    ).pipe(map((res) => res.body));
  }

  retireCylinderUnit(cylinderUnitId: string): Observable<CylinderUnitResponse> {
    return retireCylinderUnitApiV1CylinderUnitsCylinderUnitIdRetirePost(
      this.http,
      this.config.rootUrl,
      { cylinder_unit_id: cylinderUnitId },
    ).pipe(map((res) => res.body));
  }
}
