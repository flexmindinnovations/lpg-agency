import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { getQuarterlyTdtRatingApiV1TdtRatingQuarterlyGet } from './generated/fn/compliance-tdt-rating/get-quarterly-tdt-rating-api-v-1-tdt-rating-quarterly-get';
import { getLiveTdtProjectionApiV1TdtRatingLiveProjectionGet } from './generated/fn/compliance-tdt-rating/get-live-tdt-projection-api-v-1-tdt-rating-live-projection-get';
import type { TdtQuarterlyRatingResponse } from './generated/models/tdt-quarterly-rating-response';

export interface TdtQuarterFilter {
  quarterStart: string;
  quarterEnd: string;
  branchId?: string | null;
}

/**
 * Thin wrapper over the generated `/tdt-rating` client functions — same
 * pattern as `WeighmentService`. Feeds the TDT rating report tab
 * (Phase 20 subsystem 2).
 */
@Injectable({ providedIn: 'root' })
export class TdtRatingService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  /** A closed or in-progress quarter given explicit bounds. `quarterEnd`
   * is the exclusive upper bound (first day *after* the quarter). */
  getQuarterlyRating(filter: TdtQuarterFilter): Observable<TdtQuarterlyRatingResponse> {
    return getQuarterlyTdtRatingApiV1TdtRatingQuarterlyGet(this.http, this.config.rootUrl, {
      quarter_start: filter.quarterStart,
      quarter_end: filter.quarterEnd,
      branch_id: filter.branchId,
    }).pipe(map((res) => res.body));
  }

  /** The still-open current calendar quarter, computed server-side "as of
   * now" — so the distributor can still act before the quarter closes. */
  getLiveProjection(branchId?: string | null): Observable<TdtQuarterlyRatingResponse> {
    return getLiveTdtProjectionApiV1TdtRatingLiveProjectionGet(this.http, this.config.rootUrl, {
      branch_id: branchId,
    }).pipe(map((res) => res.body));
  }
}
