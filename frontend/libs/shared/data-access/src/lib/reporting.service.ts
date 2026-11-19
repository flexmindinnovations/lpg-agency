import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getDailySalesApiV1ReportingSalesGet } from './generated/fn/reporting/get-daily-sales-api-v-1-reporting-sales-get';
import { getDriverPerformanceApiV1ReportingDriversGet } from './generated/fn/reporting/get-driver-performance-api-v-1-reporting-drivers-get';
import type { DailySalesResponse } from './generated/models/daily-sales-response';
import type { DriverPerformanceResponse } from './generated/models/driver-performance-response';

/** Inclusive `YYYY-MM-DD` range, optionally for one branch. */
export interface ReportRange {
  startDate: string;
  endDate: string;
  branchId?: string | null;
}

/**
 * Thin wrapper over the generated `/reporting` client functions (same pattern
 * as `TdtRatingService`). Feeds the dashboard's revenue and driver widgets.
 */
@Injectable({ providedIn: 'root' })
export class ReportingService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  /** Invoiced revenue per day (and branch) for the range. */
  dailySales(range: ReportRange): Observable<DailySalesResponse[]> {
    return getDailySalesApiV1ReportingSalesGet(this.http, this.config.rootUrl, {
      start_date: range.startDate,
      end_date: range.endDate,
      branch_id: range.branchId,
    }).pipe(map((res) => res.body));
  }

  /** Stops delivered, failed and cash per driver per day for the range. */
  driverPerformance(range: ReportRange): Observable<DriverPerformanceResponse[]> {
    return getDriverPerformanceApiV1ReportingDriversGet(this.http, this.config.rootUrl, {
      start_date: range.startDate,
      end_date: range.endDate,
      branch_id: range.branchId,
    }).pipe(map((res) => res.body));
  }
}
