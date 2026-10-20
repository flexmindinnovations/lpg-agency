import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listCashHandoverRegisterApiV1CashHandoversGet } from './generated/fn/cash-handovers/list-cash-handover-register-api-v-1-cash-handovers-get';
import { reviewCashHandoverApiV1CashHandoversCashHandoverIdReviewPost } from './generated/fn/cash-handovers/review-cash-handover-api-v-1-cash-handovers-cash-handover-id-review-post';
import type { CashHandoverRegisterEntryResponse } from './generated/models/cash-handover-register-entry-response';
import type { CashHandoverReviewResponse } from './generated/models/cash-handover-review-response';

export interface CashHandoverRegisterFilter {
  /** IST calendar days, `YYYY-MM-DD`, inclusive. */
  readonly declaredFrom?: string | null;
  readonly declaredTo?: string | null;
  /** `pending`, `accepted` or `disputed`. */
  readonly reviewStatus?: string | null;
}

/** The accountant's cash handover register (DA-33). */
@Injectable({ providedIn: 'root' })
export class CashHandoverService {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  listRegister(
    filter: CashHandoverRegisterFilter,
  ): Observable<CashHandoverRegisterEntryResponse[]> {
    return listCashHandoverRegisterApiV1CashHandoversGet(this.http, this.config.rootUrl, {
      declared_from: filter.declaredFrom || undefined,
      declared_to: filter.declaredTo || undefined,
      review_status: filter.reviewStatus || undefined,
    }).pipe(map((res) => res.body));
  }

  review(
    cashHandoverId: string,
    outcome: 'accepted' | 'disputed',
    note: string | null,
  ): Observable<CashHandoverReviewResponse> {
    return reviewCashHandoverApiV1CashHandoversCashHandoverIdReviewPost(
      this.http,
      this.config.rootUrl,
      { cash_handover_id: cashHandoverId, body: { outcome, note: note?.trim() || null } },
    ).pipe(map((res) => res.body));
  }
}
