import type {
  CashInHandResponse,
  DailySalesResponse,
  DriverPerformanceResponse,
  OperationsSnapshotResponse,
  RefillDueCustomerResponse,
  ReorderSignalResponse,
  TdtQuarterlyRatingResponse,
} from '@lpg/shared/data-access';
import { addDays, dateRange, shortDate } from './dashboard-dates';

/**
 * Pure projections from API payloads to what the widgets show. Nothing here
 * touches the DOM or ECharts, so the maths (deltas, bins, ranking) is unit
 * tested directly.
 */

// ---- Numbers --------------------------------------------------------------

/** "₹1.2 L", "₹3.4 Cr" for large rupee amounts; full grouping below a lakh. */
export function compactInr(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  const fmt = (n: number) => n.toLocaleString('en-IN', { maximumFractionDigits: 1 });
  if (abs >= 1e7) return `${sign}₹${fmt(abs / 1e7)} Cr`;
  if (abs >= 1e5) return `${sign}₹${fmt(abs / 1e5)} L`;
  return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export interface Delta {
  /** "+12%", "-3%", "0%". */
  readonly text: string;
  readonly direction: 'up' | 'down' | 'flat';
}

/** Change of `current` against `previous`; `null` when there is nothing to compare with. */
export function percentChange(current: number, previous: number): Delta | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous === 0) return null;
  const pct = Math.round(((current - previous) / previous) * 100);
  if (pct === 0) return { text: '0%', direction: 'flat' };
  return { text: `${pct > 0 ? '+' : '-'}${Math.abs(pct)}%`, direction: pct > 0 ? 'up' : 'down' };
}

// ---- Time series ----------------------------------------------------------

/** Revenue (taxable value, so collected GST is not mistaken for income) per day, across branches. */
export function revenueByDay(rows: readonly DailySalesResponse[]): Map<string, number> {
  const byDay = new Map<string, number>();
  for (const row of rows) {
    const amount = Number(row.taxable_value ?? row.total_revenue) || 0;
    byDay.set(row.sale_date, (byDay.get(row.sale_date) ?? 0) + amount);
  }
  return byDay;
}

/** Delivered stops per day, across drivers. */
export function deliveredByDay(rows: readonly DriverPerformanceResponse[]): Map<string, number> {
  const byDay = new Map<string, number>();
  for (const row of rows) {
    byDay.set(row.date, (byDay.get(row.date) ?? 0) + row.delivered_stops);
  }
  return byDay;
}

/** A value for every day in [start, end], zero where the series has no entry. */
export function series(byDay: ReadonlyMap<string, number>, start: string, end: string): number[] {
  return dateRange(start, end).map((day) => byDay.get(day) ?? 0);
}

export interface RevenueTrend {
  readonly days: readonly string[];
  readonly current: readonly number[];
  /** The period of the same length immediately before, aligned day by day. */
  readonly previous: readonly number[];
  readonly previousDays: readonly string[];
  readonly currentTotal: number;
  readonly previousTotal: number;
}

/** The last `length` days ending `end`, against the `length` days before them. */
export function revenueTrend(
  rows: readonly DailySalesResponse[],
  end: string,
  length: number,
): RevenueTrend {
  const byDay = revenueByDay(rows);
  const start = addDays(end, -(length - 1));
  const previousEnd = addDays(start, -1);
  const previousStart = addDays(previousEnd, -(length - 1));
  const current = series(byDay, start, end);
  const previous = series(byDay, previousStart, previousEnd);
  const sum = (xs: readonly number[]) => xs.reduce((a, b) => a + b, 0);
  return {
    days: dateRange(start, end),
    current,
    previous,
    previousDays: dateRange(previousStart, previousEnd),
    currentTotal: sum(current),
    previousTotal: sum(previous),
  };
}

// ---- Order pipeline -------------------------------------------------------

export interface PipelineStage {
  readonly key: string;
  readonly label: string;
  readonly count: number;
  readonly kind: 'open' | 'done' | 'failed';
}

const OPEN_STAGES: readonly (readonly [string, string])[] = [
  ['booked', 'Booked'],
  ['confirmed', 'Confirmed'],
  ['assigned', 'Assigned'],
  ['ready_for_dispatch', 'Ready to dispatch'],
  ['out_for_delivery', 'Out for delivery'],
];

/** The day's orders in lifecycle order, left to right. */
export function pipelineStages(orders: OperationsSnapshotResponse['orders']): PipelineStage[] {
  return [
    ...OPEN_STAGES.map(([key, label]): PipelineStage => ({
      key,
      label,
      count: orders.open_by_status[key] ?? 0,
      kind: 'open',
    })),
    { key: 'delivered', label: 'Delivered today', count: orders.delivered_today, kind: 'done' },
    { key: 'failed', label: 'Failed today', count: orders.failed_today, kind: 'failed' },
  ];
}

// ---- Drivers --------------------------------------------------------------

export interface DriverToday {
  readonly name: string;
  readonly delivered: number;
  readonly failed: number;
  readonly pending: number;
  readonly total: number;
}

/** Today's stops per driver, busiest first. */
export function driversToday(
  rows: readonly DriverPerformanceResponse[],
  today: string,
  limit = 8,
): DriverToday[] {
  const byDriver = new Map<string, DriverToday>();
  for (const row of rows) {
    if (row.date !== today) continue;
    const failed = row.failed_stops ?? 0;
    const entry = byDriver.get(row.driver_id);
    const delivered = (entry?.delivered ?? 0) + row.delivered_stops;
    const failedTotal = (entry?.failed ?? 0) + failed;
    const total = (entry?.total ?? 0) + row.total_stops;
    byDriver.set(row.driver_id, {
      name: row.driver_name,
      delivered,
      failed: failedTotal,
      pending: Math.max(total - delivered - failedTotal, 0),
      total,
    });
  }
  return [...byDriver.values()].sort((a, b) => b.total - a.total).slice(0, limit);
}

// ---- Cash -----------------------------------------------------------------

export interface DriverCash {
  readonly name: string;
  readonly cash: number;
  readonly upi: number;
  readonly routes: number;
  readonly oldest: string;
}

/** Cash each driver is carrying, largest first. */
export function cashByDriver(response: CashInHandResponse, limit = 8): DriverCash[] {
  return response.drivers
    .map((d) => ({
      name: d.driver_name,
      cash: Number(d.cash_amount) || 0,
      upi: Number(d.upi_amount) || 0,
      routes: d.route_count,
      oldest: d.oldest_route_date,
    }))
    .sort((a, b) => b.cash - a.cash)
    .slice(0, limit);
}

// ---- Stock ----------------------------------------------------------------

export interface StockStatus {
  readonly key: string;
  readonly label: string;
  readonly quantity: number;
}

const STOCK_ORDER: readonly (readonly [string, string])[] = [
  ['filled', 'Filled'],
  ['empty', 'Empty'],
  ['damaged', 'Damaged'],
  ['leakage', 'Leakage'],
  ['quarantine', 'Quarantine'],
  ['repair', 'In repair'],
  ['scrap', 'Scrap'],
];

/** Cylinder counts by status in a fixed order, skipping statuses with none. */
export function stockStatuses(byStatus: Readonly<Record<string, number>>): StockStatus[] {
  return STOCK_ORDER.map(([key, label]) => ({ key, label, quantity: byStatus[key] ?? 0 })).filter(
    (s) => s.quantity > 0,
  );
}

// ---- Reorder --------------------------------------------------------------

export interface ReorderBullet {
  readonly label: string;
  readonly onHand: number;
  readonly reorderPoint: number;
  readonly safetyStock: number;
  /** At or below the safety stock. */
  readonly critical: boolean;
}

/** Locations at or near their reorder point, emptiest relative to the point first. */
export function reorderBullets(
  signals: readonly ReorderSignalResponse[],
  typeNames: ReadonlyMap<string, string>,
  limit = 8,
): ReorderBullet[] {
  const seen = new Map<string, number>();
  return signals
    .map((s) => {
      const base = typeNames.get(s.cylinder_type_id) ?? 'Cylinder';
      const n = (seen.get(base) ?? 0) + 1;
      seen.set(base, n);
      return { s, base, n };
    })
    .map(({ s, base, n }) => ({
      label: n > 1 ? `${base} (${n})` : base,
      onHand: s.on_hand,
      reorderPoint: s.reorder_point,
      safetyStock: s.safety_stock,
      critical: s.on_hand <= s.safety_stock,
    }))
    .sort((a, b) => a.onHand / (a.reorderPoint || 1) - b.onHand / (b.reorderPoint || 1))
    .slice(0, limit);
}

// ---- Delivery-time rating -------------------------------------------------

export interface RatingBand {
  readonly stars: number;
  readonly orders: number;
  readonly share: number;
}

/** Share of the quarter's orders in each star band, 5 stars first. */
export function ratingBands(rating: TdtQuarterlyRatingResponse): RatingBand[] {
  const total = rating.total_orders || 0;
  return [...rating.distribution]
    .sort((a, b) => b.stars - a.stars)
    .map((band) => ({
      stars: band.stars,
      orders: band.order_count,
      share: total > 0 ? Math.round((band.order_count / total) * 1000) / 10 : 0,
    }));
}

// ---- Refills --------------------------------------------------------------

export interface RefillBin {
  readonly key: string;
  readonly label: string;
  readonly count: number;
  readonly overdue: boolean;
}

/** An "Overdue" bin, then one bin per day for the next `days` days. */
export function refillBins(
  items: readonly RefillDueCustomerResponse[],
  today: string,
  days = 14,
): RefillBin[] {
  const counts = new Map<string, number>();
  let overdue = 0;
  for (const item of items) {
    const due = item.refill_due_date.slice(0, 10);
    if (due < today) overdue += 1;
    else counts.set(due, (counts.get(due) ?? 0) + 1);
  }
  return [
    { key: 'overdue', label: 'Overdue', count: overdue, overdue: true },
    ...dateRange(today, addDays(today, days - 1)).map((day) => ({
      key: day,
      label: shortDate(day),
      count: counts.get(day) ?? 0,
      overdue: false,
    })),
  ];
}

// ---- Attention queue ------------------------------------------------------

export type AttentionSeverity = 'critical' | 'warning' | 'info';

export interface AttentionItem {
  readonly key: string;
  readonly severity: AttentionSeverity;
  readonly count: number;
  readonly text: string;
  readonly detail?: string;
  readonly route: string;
}

const SEVERITY_RANK: Record<AttentionSeverity, number> = { critical: 0, warning: 1, info: 2 };

/** What is waiting on someone right now, most urgent first; empty when nothing is. */
export function attentionItems(
  ops: OperationsSnapshotResponse,
  formatMoney: (value: unknown) => string,
): AttentionItem[] {
  const open = ops.orders.open_by_status;
  const waitingForTrip =
    (open['confirmed'] ?? 0) + (open['assigned'] ?? 0) + (open['ready_for_dispatch'] ?? 0);
  const items: AttentionItem[] = [
    {
      key: 'failed',
      severity: 'critical',
      count: ops.orders.failed_today,
      text: 'deliveries failed today',
      route: '/orders',
    },
    {
      key: 'low-stock',
      severity: 'critical',
      count: ops.low_stock_count,
      text: 'locations at or below their reorder point',
      route: '/inventory',
    },
    {
      key: 'cancellations',
      severity: 'warning',
      count: ops.orders.pending_cancellations,
      text: 'cancellations waiting for approval',
      route: '/orders',
    },
    {
      key: 'complaints',
      severity: 'warning',
      count: ops.open_complaints,
      text: 'open complaints',
      route: '/complaints',
    },
    {
      key: 'booked',
      severity: 'info',
      count: open['booked'] ?? 0,
      text: 'orders awaiting confirmation',
      route: '/orders',
    },
    {
      key: 'trip',
      severity: 'info',
      count: waitingForTrip,
      text: 'orders waiting for a trip',
      route: '/dispatch',
    },
  ];
  if (ops.invoices) {
    items.push({
      key: 'on-hold',
      severity: 'warning',
      count: ops.invoices.on_hold_count,
      text: 'invoices on hold',
      route: '/invoices',
    });
  }
  if (ops.cash) {
    items.push({
      key: 'handovers',
      severity: 'warning',
      count: ops.cash.handovers_awaiting_review,
      text: 'cash handovers to verify',
      detail: `${formatMoney(ops.cash.awaiting_handover)} still with drivers`,
      route: '/cash-handovers',
    });
  }
  return items
    .filter((item) => item.count > 0)
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || b.count - a.count);
}
