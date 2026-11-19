import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router } from '@angular/router';
import {
  ActivityListComponent,
  type ActivityItem,
  type ActivityStatusTone,
  ChartCardComponent,
  type ChartCardState,
  type ChartTheme,
  ChartThemeService,
  EmptyStateComponent,
  formatEntityName,
  formatTimestamp,
  HasPermissionDirective,
  SectionCardComponent,
  SkeletonComponent,
  toSentenceCase,
} from '@lpg/shared/ui';
import { ChartComponent } from '@lpg/shared/ui/charts';
import {
  type ChartSpec,
  cashChart,
  driversChart,
  pipelineChart,
  ratingChart,
  refillsChart,
  reorderChart,
  revenueChart,
  stockChart,
} from './chart-options';
import { DashboardData, TREND_DAYS, type WidgetData } from './dashboard-data';
import {
  cashByDriver,
  compactInr,
  driversToday,
  percentChange,
  pipelineStages,
  ratingBands,
  refillBins,
  reorderBullets,
  revenueTrend,
  stockStatuses,
} from './dashboard-model';

const ACTION_ICON: Record<string, string> = {
  create: 'pi pi-plus-circle',
  update: 'pi pi-pencil',
  delete: 'pi pi-trash',
};
const ACTION_LABEL: Record<string, string> = {
  create: 'Created',
  update: 'Changed',
  delete: 'Deleted',
};
const ACTION_TONE: Record<string, ActivityStatusTone> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
};

/** Every chart card is this tall, so the grid reads as one even board. */
const CHART_HEIGHT = 280;

/**
 * The charts of the Home dashboard. The cards show at once; each chart loads
 * into its card with `@defer`, so ECharts stays out of the initial bundle.
 */
@Component({
  selector: 'lpg-home-charts',
  standalone: true,
  imports: [
    ActivityListComponent,
    ChartCardComponent,
    ChartComponent,
    EmptyStateComponent,
    HasPermissionDirective,
    SectionCardComponent,
    SkeletonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="charts">
      <lpg-chart-card
        class="charts__wide"
        heading="Order pipeline"
        subtitle="Where today's orders are, from booking to delivery"
        [state]="state(data.operations, pipeline())"
        [table]="pipeline()?.table ?? null"
        [link]="{ label: 'Orders', route: '/orders' }"
        [height]="chartHeight"
        emptyTitle="No orders yet today"
        emptyDescription="Orders show here as they are booked."
      >
        @if (pipeline(); as spec) {
          @defer (on idle) {
            <lpg-chart [option]="spec.option" [label]="spec.label" (markClick)="go('/orders')" />
          } @placeholder {
            <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
          }
        }
      </lpg-chart-card>

      @if (data.drivers.visible()) {
        <lpg-chart-card
          heading="Drivers today"
          subtitle="Stops delivered, failed and still to do"
          [state]="state(data.drivers, drivers())"
          [table]="drivers()?.table ?? null"
          [link]="{ label: 'Dispatch', route: '/dispatch' }"
          [height]="chartHeight"
          emptyTitle="No trips today"
          emptyDescription="Drivers appear here once a trip is dispatched."
        >
          @if (drivers(); as spec) {
            @defer (on idle) {
              <lpg-chart
                [option]="spec.option"
                [label]="spec.label"
                (markClick)="go('/dispatch')"
              />
            } @placeholder {
              <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
            }
          }
        </lpg-chart-card>
      }

      @if (data.sales.visible()) {
        <lpg-chart-card
          class="charts__wide"
          heading="Revenue"
          [subtitle]="revenueSubtitle()"
          [state]="state(data.sales, revenue())"
          [table]="revenue()?.table ?? null"
          [link]="{ label: 'Invoices', route: '/invoices' }"
          [height]="chartHeight"
          emptyTitle="No invoices in this period"
          emptyDescription="Revenue appears here once invoices are issued."
        >
          @if (revenue(); as spec) {
            @defer (on idle) {
              <lpg-chart [option]="spec.option" [label]="spec.label" />
            } @placeholder {
              <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
            }
          }
        </lpg-chart-card>
      }

      @if (data.cash.visible()) {
        <lpg-chart-card
          heading="Cash on the road"
          [subtitle]="cashSubtitle()"
          [state]="state(data.cash, cash())"
          [table]="cash()?.table ?? null"
          [link]="{ label: 'Handovers', route: '/cash-handovers' }"
          [height]="chartHeight"
          emptyTitle="No cash with drivers"
          emptyDescription="Cash collected on routes shows here until it is handed over."
        >
          @if (cash(); as spec) {
            @defer (on idle) {
              <lpg-chart
                [option]="spec.option"
                [label]="spec.label"
                (markClick)="go('/cash-handovers')"
              />
            } @placeholder {
              <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
            }
          }
        </lpg-chart-card>
      }

      <ng-container *lpgHasPermission="'inventory:read'">
        <lpg-chart-card
          heading="Cylinder stock"
          subtitle="By status, across all locations"
          [state]="state(data.summary, stock())"
          [table]="stock()?.table ?? null"
          [link]="{ label: 'Inventory', route: '/inventory' }"
          [height]="chartHeight"
          emptyTitle="No stock recorded yet"
          emptyDescription="Cylinder movements appear here once stock is received."
        >
          @if (stock(); as spec) {
            @defer (on idle) {
              <lpg-chart
                [option]="spec.option"
                [label]="spec.label"
                (markClick)="go('/inventory')"
              />
            } @placeholder {
              <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
            }
          }
        </lpg-chart-card>

        @if (data.reorder.visible()) {
          <lpg-chart-card
            heading="Close to reorder"
            subtitle="On hand against the reorder point (the black tick)"
            [state]="state(data.reorder, reorder())"
            [table]="reorder()?.table ?? null"
            [link]="{ label: 'Inventory', route: '/inventory' }"
            [height]="chartHeight"
            emptyTitle="Every location is above its reorder point"
            emptyDescription="Locations show here when stock falls to the point you set."
          >
            @if (reorder(); as spec) {
              @defer (on idle) {
                <lpg-chart
                  [option]="spec.option"
                  [label]="spec.label"
                  (markClick)="go('/inventory')"
                />
              } @placeholder {
                <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
              }
            }
          </lpg-chart-card>
        }
      </ng-container>

      @if (data.rating.visible()) {
        <lpg-chart-card
          heading="Delivery-time rating"
          [subtitle]="ratingSubtitle()"
          [state]="state(data.rating, rating())"
          [table]="rating()?.table ?? null"
          [link]="{ label: 'Report', route: '/reports/tdt-rating' }"
          [height]="chartHeight"
          emptyTitle="No deliveries this quarter yet"
          emptyDescription="The projection builds up as orders are delivered."
        >
          @if (rating(); as spec) {
            @defer (on idle) {
              <lpg-chart
                [option]="spec.option"
                [label]="spec.label"
                (markClick)="go('/reports/tdt-rating')"
              />
            } @placeholder {
              <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
            }
          }
        </lpg-chart-card>
      }

      <ng-container *lpgHasPermission="'customers:read'">
        @if (data.refills.visible()) {
          <lpg-chart-card
            class="charts__wide"
            heading="Refills due"
            subtitle="Customers predicted to need a refill in the next 14 days"
            [state]="state(data.refills, refills())"
            [table]="refills()?.table ?? null"
            [link]="{ label: 'Customers', route: '/customers' }"
            [height]="chartHeight"
            emptyTitle="No refills due"
            emptyDescription="Predicted dates are refreshed nightly from delivery history."
          >
            @if (refills(); as spec) {
              @defer (on idle) {
                <lpg-chart
                  [option]="spec.option"
                  [label]="spec.label"
                  (markClick)="go('/customers')"
                />
              } @placeholder {
                <lpg-skeleton variant="block" [height]="chartHeight + 'px'" />
              }
            }
          </lpg-chart-card>
        }
      </ng-container>

      <lpg-section-card *lpgHasPermission="'audit:read'" heading="Recent activity">
        @if (activity().length > 0) {
          <lpg-activity-list [items]="activity()" />
        } @else {
          <lpg-empty-state
            title="No recent activity"
            description="Actions across the platform will show up here."
          />
        }
      </lpg-section-card>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .charts {
        display: grid;
        grid-template-columns: repeat(12, minmax(0, 1fr));
        gap: var(--spacing-lg);
      }

      .charts > * {
        grid-column: span 12;
      }

      /* Cards in a row are the same height. */
      .charts {
        grid-auto-rows: 1fr;
      }

      /* Two widgets per row from tablet width, a wide and a narrow one. */
      @media (min-width: 900px) {
        .charts > * {
          grid-column: span 6;
        }

        .charts > .charts__wide {
          grid-column: span 12;
        }
      }

      @media (min-width: 1280px) {
        .charts > * {
          grid-column: span 4;
        }

        .charts > .charts__wide {
          grid-column: span 8;
        }
      }
    `,
  ],
})
export class HomeCharts {
  protected readonly data = inject(DashboardData);
  protected readonly chartHeight = CHART_HEIGHT;
  private readonly theme = inject(ChartThemeService).theme;
  private readonly router = inject(Router);

  /** Builds a widget's chart once both its data and the theme are known. */
  private spec<T>(
    widget: WidgetData<T>,
    build: (value: T, theme: ChartTheme) => ChartSpec,
  ): ChartSpec | null {
    const value = widget.data();
    const theme = this.theme();
    if (value === null || theme === null) return null;
    // A payload that does not fit the chart must break that widget only, never
    // the rest of the dashboard.
    try {
      return build(value, theme);
    } catch {
      return null;
    }
  }

  protected readonly pipeline = computed(() =>
    this.spec(this.data.operations, (ops, t) => pipelineChart(pipelineStages(ops.orders), t)),
  );
  protected readonly drivers = computed(() =>
    this.spec(this.data.drivers, (rows, t) => driversChart(driversToday(rows, this.data.today), t)),
  );
  protected readonly cash = computed(() =>
    this.spec(this.data.cash, (response, t) => cashChart(cashByDriver(response), t)),
  );
  protected readonly revenue = computed(() =>
    this.spec(this.data.sales, (rows, t) =>
      revenueChart(revenueTrend(rows, this.data.today, TREND_DAYS), t),
    ),
  );
  protected readonly stock = computed(() =>
    this.spec(this.data.summary, (summary, t) =>
      stockChart(stockStatuses(summary.inventory_by_status), t),
    ),
  );
  protected readonly reorder = computed(() => {
    const names = new Map(
      (this.data.summary.data()?.price_cards ?? []).map(
        (card) => [card.cylinder_type_id, card.name] as const,
      ),
    );
    return this.spec(this.data.reorder, (signals, t) =>
      reorderChart(reorderBullets(signals, names), t),
    );
  });
  protected readonly rating = computed(() =>
    this.spec(this.data.rating, (rating, t) =>
      ratingChart(ratingBands(rating), rating.overall_stars, t),
    ),
  );
  protected readonly refills = computed(() =>
    this.spec(this.data.refills, (items, t) => refillsChart(refillBins(items, this.data.today), t)),
  );

  /** The latest audit entries: a lighter view than the full audit log. */
  protected readonly activity = computed<ActivityItem[]>(() =>
    (this.data.summary.data()?.recent_activity ?? []).slice(0, 4).map((entry) => ({
      time: formatTimestamp(entry.performed_at),
      icon: ACTION_ICON[entry.action] ?? 'pi pi-circle',
      title: entry.entity_display_name
        ? `${formatEntityName(entry.entity_name)} ${entry.entity_display_name}`
        : formatEntityName(entry.entity_name),
      description: entry.actor_display_name ? `by ${entry.actor_display_name}` : undefined,
      status: entry.action
        ? (ACTION_LABEL[entry.action] ?? toSentenceCase(entry.action))
        : undefined,
      statusTone: ACTION_TONE[entry.action] ?? 'neutral',
    })),
  );

  protected readonly revenueSubtitle = computed(() => {
    const rows = this.data.sales.data();
    if (!rows) return `Last ${TREND_DAYS} days, against the ${TREND_DAYS} before`;
    const trend = revenueTrend(rows, this.data.today, TREND_DAYS);
    const change = percentChange(trend.currentTotal, trend.previousTotal);
    return `${compactInr(trend.currentTotal)} in ${TREND_DAYS} days${change ? `, ${change.text} on the ${TREND_DAYS} before` : ''}. Before GST.`;
  });

  protected readonly cashSubtitle = computed(() => {
    const total = this.data.cash.data()?.total_cash;
    return total === undefined
      ? 'Collected on routes, not yet handed over'
      : `${compactInr(Number(total))} with drivers, not yet handed over`;
  });

  protected readonly ratingSubtitle = computed(() => {
    const stars = this.data.rating.data()?.overall_stars;
    return typeof stars === 'number'
      ? `${stars} ${stars === 1 ? 'star' : 'stars'} if this quarter ended now. A projection.`
      : "Share of this quarter's orders by delivery time";
  });

  /** Skeleton only on the first load; after that the chart keeps its data. */
  protected state(widget: WidgetData<unknown>, spec: ChartSpec | null): ChartCardState {
    const status = widget.status();
    if (spec === null) return status === 'loading' ? 'loading' : 'error';
    return spec.empty ? 'empty' : 'ready';
  }

  protected go(route: string): void {
    void this.router.navigateByUrl(route);
  }
}
