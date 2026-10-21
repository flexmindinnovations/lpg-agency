import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

import { getDashboardSummaryApiV1DashboardSummaryGet } from './generated/fn/dashboard/get-dashboard-summary-api-v-1-dashboard-summary-get';

import { getOperationsSnapshotApiV1DashboardOperationsGet } from './generated/fn/dashboard/get-operations-snapshot-api-v-1-dashboard-operations-get';

import type { DashboardSummaryResponse } from './generated/models/dashboard-summary-response';
import type { OperationsSnapshotResponse } from './generated/models/operations-snapshot-response';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  getSummary(): Observable<DashboardSummaryResponse> {
    return getDashboardSummaryApiV1DashboardSummaryGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  /** Today's operations KPIs (DO-28). Invoice and cash figures are `null`
   * for callers without the permission to see them. */
  getOperations(): Observable<OperationsSnapshotResponse> {
    return getOperationsSnapshotApiV1DashboardOperationsGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }
}
