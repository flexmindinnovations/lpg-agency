import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from './generated/api-configuration';
import { listCashHandoverRegisterApiV1CashHandoversGet } from './generated/fn/cash-handovers/list-cash-handover-register-api-v-1-cash-handovers-get';
import { reviewCashHandoverApiV1CashHandoversCashHandoverIdReviewPost } from './generated/fn/cash-handovers/review-cash-handover-api-v-1-cash-handovers-cash-handover-id-review-post';
import { getCashBookApiV1CashHandoversCashBookGet } from './generated/fn/cash-handovers/get-cash-book-api-v-1-cash-handovers-cash-book-get';
import { listCashInHandApiV1CashHandoversCashInHandGet } from './generated/fn/cash-handovers/list-cash-in-hand-api-v-1-cash-handovers-cash-in-hand-get';
import type { CashBookResponse } from './generated/models/cash-book-response';
import type { CashInHandResponse } from './generated/models/cash-in-hand-response';
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

  /** What each driver is carrying: collected on routes not yet handed over. */
  cashInHand(): Observable<CashInHandResponse> {
    return listCashInHandApiV1CashHandoversCashInHandGet(this.http, this.config.rootUrl).pipe(
      map((res) => res.body),
    );
  }

  /** One IST day (`YYYY-MM-DD`): money in by mode and the fate of the cash. */
  cashBook(day: string): Observable<CashBookResponse> {
    return getCashBookApiV1CashHandoversCashBookGet(this.http, this.config.rootUrl, {
      date: day,
    }).pipe(map((res) => res.body));
  }
}
