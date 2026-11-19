import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { type Observable, debounceTime, map } from 'rxjs';
import {
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

  load(source: Observable<T>): void {
    const ticket = ++this.latest;
    source.subscribe({
      next: (value) => {
        if (ticket !== this.latest) return;
        this.data.set(value);
        this.status.set('ready');
      },
      error: (error: unknown) => {
        if (ticket !== this.latest) return;
        if (error instanceof HttpErrorResponse && error.status === 403) {
          this.status.set('forbidden');
        } else {
          this.status.set(this.data() === null ? 'error' : 'ready');
        }
      },
    });
  }
}

/**
 * Every call the Home dashboard makes, one `WidgetData` each, so a slow or
 * failing endpoint only affects its own widget. Provided by the Home page,
 * so it lives and dies with it.
 */
@Injectable()
export class DashboardData {
  private readonly dashboard = inject(DashboardService);
  private readonly reporting = inject(ReportingService);
  private readonly cashService = inject(CashHandoverService);
  private readonly inventory = inject(InventoryService);
  private readonly customers = inject(CustomerService);
  private readonly tdt = inject(TdtRatingService);
  private readonly socket = inject(WebSocketService);

  readonly today = istDate();

  readonly operations = new WidgetData<OperationsSnapshotResponse>();
  readonly summary = new WidgetData<DashboardSummaryResponse>();
  readonly sales = new WidgetData<DailySalesResponse[]>();
  readonly drivers = new WidgetData<DriverPerformanceResponse[]>();
  readonly cash = new WidgetData<CashInHandResponse>();
  readonly reorder = new WidgetData<ReorderSignalResponse[]>();
  readonly rating = new WidgetData<TdtQuarterlyRatingResponse>();
  readonly refills = new WidgetData<RefillDueCustomerResponse[]>();

  constructor() {
    this.loadAll();

    // Orders and trips change through the day: refresh what they feed, after a
    // quiet second so a burst (a whole trip delivered) is one refetch.
    this.socket.subscribeTo('dashboard');
    this.socket.subscribeTo('orders');
    this.socket
      .changes$('dashboard.metrics_stale', 'order.status_changed')
      .pipe(debounceTime(1000), takeUntilDestroyed())
      .subscribe(() => this.refreshOperational());
  }

  private loadAll(): void {
    this.refreshOperational();
    this.summary.load(this.dashboard.getSummary());
    this.sales.load(
      this.reporting.dailySales({
        startDate: addDays(this.today, -(TREND_DAYS * 2 - 1)),
        endDate: this.today,
      }),
    );
    this.reorder.load(this.inventory.listReorderSignals());
    this.rating.load(this.tdt.getLiveProjection());
    this.refills.load(this.customers.listRefillDue(14).pipe(map((response) => response.items)));
  }

  /** The figures that move with today's orders and trips. */
  refreshOperational(): void {
    this.operations.load(this.dashboard.getOperations());
    this.drivers.load(
      this.reporting.driverPerformance({
        startDate: addDays(this.today, -(KPI_HISTORY_DAYS - 1)),
        endDate: this.today,
      }),
    );
    this.cash.load(this.cashService.cashInHand());
  }
}
