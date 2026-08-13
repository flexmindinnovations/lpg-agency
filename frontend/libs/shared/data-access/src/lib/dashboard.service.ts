import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';

import { getDashboardSummaryApiV1DashboardSummaryGet } from './generated/fn/dashboard/get-dashboard-summary-api-v-1-dashboard-summary-get';

import type { DashboardSummaryResponse } from './generated/models/dashboard-summary-response';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  getSummary(): Observable<DashboardSummaryResponse> {
    return getDashboardSummaryApiV1DashboardSummaryGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }
}
