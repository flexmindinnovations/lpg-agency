import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { type Observable, debounceTime, map } from 'rxjs';
import {
  AuthService,
  CashHandoverService,
  CustomerService,
  DashboardService,
  type DashboardSummaryResponse,
  InventoryService,
  type OperationsSnapshotResponse,
  ReportingService,
  TdtRatingService,
  WebSocketService,
  type CashInHandResponse,
  type DailySalesResponse,
  type DriverPerformanceResponse,
  type RefillDueCustomerResponse,
  type ReorderSignalResponse,
  type TdtQuarterlyRatingResponse,
} from '@lpg/shared/data-access';
import { addDays, istDate } from './dashboard-dates';

/** How many days the revenue and KPI trends look back, each side of the comparison. */
export const TREND_DAYS = 30;
/** Enough history for "same weekday last week" next to a 7-day sparkline. */
const KPI_HISTORY_DAYS = 14;

export type WidgetStatus = 'loading' | 'ready' | 'error' | 'forbidden';

/** How long the figures that move with today's orders and trips are trusted. */
const OPERATIONAL_STALE_MS = 30_000;
/** How long the slower figures (stock, sales history, ratings) are trusted. */
const REFERENCE_STALE_MS = 120_000;

/**
 * One widget's data: it keeps the last good value across refreshes, so a
 * refetch swaps numbers in place instead of flashing back to a skeleton, and
 * a failed refresh keeps showing what it had.
 */
export class WidgetData<T> {
  readonly data = signal<T | null>(null);
  readonly status = signal<WidgetStatus>('loading');
  /** Hidden entirely when the caller is not allowed to see it. */
  readonly visible = computed(() => this.status() !== 'forbidden');
  private latest = 0;
  private inFlight = false;

  /** Nothing to show and nothing on its way: worth asking the API again. */
  get needsLoad(): boolean {
    return this.data() === null && this.status() !== 'forbidden' && !this.inFlight;
  }

  load(source: Observable<T>): void {
    const ticket = ++this.latest;
    this.inFlight = true;
    source.subscribe({
      next: (value) => {
        if (ticket !== this.latest) return;
        this.inFlight = false;
        this.data.set(value);
        this.status.set('ready');
      },
      error: (error: unknown) => {
        if (ticket !== this.latest) return;
        this.inFlight = false;
        if (error instanceof HttpErrorResponse && error.status === 403) {
          this.status.set('forbidden');
        } else {
          this.status.set(this.data() === null ? 'error' : 'ready');
        }
      },
    });
  }

  /** Forget everything, and ignore any answer still on its way. */
  reset(): void {
    this.latest++;
    this.inFlight = false;
    this.data.set(null);
    this.status.set('loading');
  }
}

/**
 * Every call the Home dashboard makes, one `WidgetData` each, so a slow or
 * failing endpoint only affects its own widget.
 *
 * It lives for the whole session, so coming back to Home shows what was
 * fetched last time at once and only asks the API again when that is stale
 * (see `connect`). The cache belongs to one signed-in user: it is cleared the
 * moment someone else (or another agency) is signed in, and when the day
 * changes.
 */
@Injectable({ providedIn: 'root' })
export class DashboardData {
  private readonly dashboard = inject(DashboardService);
  private readonly reporting = inject(ReportingService);
  private readonly cashService = inject(CashHandoverService);
  private readonly inventory = inject(InventoryService);
  private readonly customers = inject(CustomerService);
  private readonly tdt = inject(TdtRatingService);
  private readonly socket = inject(WebSocketService);
  private readonly auth = inject(AuthService);

  private day = istDate();
  private owner = '';
  private visits = 0;
  private operationalAt = 0;
  private referenceAt = 0;

  /** The business day (IST) the figures are for. */
  get today(): string {
    return this.day;
  }

  /** True when Home has already been shown to this user, so entrance
   *  animations (which say "this just arrived") should not play again. */
  isRevisit = false;

  readonly operations = new WidgetData<OperationsSnapshotResponse>();
  readonly summary = new WidgetData<DashboardSummaryResponse>();
  readonly sales = new WidgetData<DailySalesResponse[]>();
  readonly drivers = new WidgetData<DriverPerformanceResponse[]>();
  readonly cash = new WidgetData<CashInHandResponse>();
  readonly reorder = new WidgetData<ReorderSignalResponse[]>();
  readonly rating = new WidgetData<TdtQuarterlyRatingResponse>();
  readonly refills = new WidgetData<RefillDueCustomerResponse[]>();

  private readonly operationalWidgets = [this.operations, this.drivers, this.cash];
  private readonly referenceWidgets = [
    this.summary,
    this.sales,
    this.reorder,
    this.rating,
    this.refills,
  ];

  /**
   * Called when Home opens. Shows the cache, refreshes in the background only
   * what is stale, and keeps today's figures live until the returned function
   * is called (when Home closes).
   */
  connect(): () => void {
    const principal = this.auth.principal();
    const owner = principal
      ? `${principal.tenantId ?? ''}|${principal.userId}|${principal.branchId ?? ''}`
      : '';
    if (owner !== this.owner || istDate() !== this.day) this.reset(owner);

    this.isRevisit = this.visits++ > 0;

    const now = Date.now();
    if (
      now - this.operationalAt > OPERATIONAL_STALE_MS ||
      this.anyNeedsLoad(this.operationalWidgets)
    ) {
      this.refreshOperational();
    }
    if (now - this.referenceAt > REFERENCE_STALE_MS || this.anyNeedsLoad(this.referenceWidgets)) {
      this.refreshReference();
    }

    // Orders and trips change through the day: refresh what they feed, after a
    // quiet second so a burst (a whole trip delivered) is one refetch.
    this.socket.subscribeTo('dashboard');
    this.socket.subscribeTo('orders');
    const live = this.socket
      .changes$('dashboard.metrics_stale', 'order.status_changed')
      .pipe(debounceTime(1000))
      .subscribe(() => this.refreshOperational());
    return () => live.unsubscribe();
  }

  /** The figures that move with today's orders and trips. */
  refreshOperational(): void {
    this.operationalAt = Date.now();
    this.operations.load(this.dashboard.getOperations());
    this.drivers.load(
      this.reporting.driverPerformance({
        startDate: addDays(this.day, -(KPI_HISTORY_DAYS - 1)),
        endDate: this.day,
      }),
    );
    this.cash.load(this.cashService.cashInHand());
  }

  /** Stock, sales history, ratings, refills: slower-moving. */
  private refreshReference(): void {
    this.referenceAt = Date.now();
    this.summary.load(this.dashboard.getSummary());
    this.sales.load(
      this.reporting.dailySales({
        startDate: addDays(this.day, -(TREND_DAYS * 2 - 1)),
        endDate: this.day,
      }),
    );
    this.reorder.load(this.inventory.listReorderSignals());
    this.rating.load(this.tdt.getLiveProjection());
    this.refills.load(this.customers.listRefillDue(14).pipe(map((response) => response.items)));
  }

  private anyNeedsLoad(widgets: readonly WidgetData<unknown>[]): boolean {
    return widgets.some((widget) => widget.needsLoad);
  }

  private reset(owner: string): void {
    this.owner = owner;
    this.day = istDate();
    this.visits = 0;
    this.operationalAt = 0;
    this.referenceAt = 0;
    [...this.operationalWidgets, ...this.referenceWidgets].forEach((widget) => widget.reset());
  }
}
