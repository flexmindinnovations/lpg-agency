import type {
  DailySalesResponse,
  DriverPerformanceResponse,
  OperationsSnapshotResponse,
  ReorderSignalResponse,
} from '@lpg/shared/data-access';
import { addDays, dateRange, istDate, shortDate } from './dashboard-dates';
import {
  attentionItems,
  cashByDriver,
  compactInr,
  deliveredByDay,
  driversToday,
  percentChange,
  pipelineStages,
  ratingBands,
  refillBins,
  reorderBullets,
  revenueTrend,
  stockStatuses,
} from './dashboard-model';

const TODAY = '2026-11-19';

function sale(date: string, taxable: string): DailySalesResponse {
  return {
    branch_id: 'b',
    sale_date: date,
    taxable_value: taxable,
    total_invoices: 1,
    total_revenue: taxable,
    total_tax: '0',
  };
}

function driverRow(
  over: Partial<DriverPerformanceResponse> & Pick<DriverPerformanceResponse, 'date'>,
): DriverPerformanceResponse {
  return {
    driver_id: 'd1',
    driver_name: 'Ravi',
    delivered_stops: 0,
    failed_stops: 0,
    total_stops: 0,
    ...over,
  };
}

function ops(over: Partial<OperationsSnapshotResponse> = {}): OperationsSnapshotResponse {
  return {
    cash: null,
    invoices: null,
    low_stock_count: 0,
    open_complaints: 0,
    payment_terms_days: 30,
    orders: {
      bookings_today: 0,
      delivered_today: 0,
      failed_today: 0,
      pending_cancellations: 0,
      open_by_status: {},
    },
    ...over,
  };
}

describe('dashboard dates', () => {
  it('does day arithmetic on plain dates, across month and year ends', () => {
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(dateRange('2026-11-17', '2026-11-19')).toEqual([
      '2026-11-17',
      '2026-11-18',
      '2026-11-19',
    ]);
  });

  it('uses the IST date, not the UTC one, for "today"', () => {
    // 20:00 UTC on the 18th is already 01:30 on the 19th in India.
    expect(istDate(new Date('2026-11-18T20:00:00Z'))).toBe('2026-11-19');
  });

  it('formats a short date', () => {
    expect(shortDate('2026-11-05')).toBe('5 Nov');
  });
});

describe('compactInr', () => {
  it.each([
    [999, '₹999'],
    [45_000, '₹45,000'],
    [148_000, '₹1.5 L'],
    [3_340_000, '₹33.4 L'],
    [25_000_000, '₹2.5 Cr'],
    [-250_000, '-₹2.5 L'],
  ])('%d is shown as %s', (value, text) => {
    expect(compactInr(value)).toBe(text);
  });
});

describe('percentChange', () => {
  it('gives a signed whole percentage with its direction', () => {
    expect(percentChange(112, 100)).toEqual({ text: '+12%', direction: 'up' });
    expect(percentChange(90, 100)).toEqual({ text: '-10%', direction: 'down' });
    expect(percentChange(100, 100)).toEqual({ text: '0%', direction: 'flat' });
  });

  it('has nothing to say when there is no baseline', () => {
    expect(percentChange(5, 0)).toBeNull();
    expect(percentChange(Number.NaN, 4)).toBeNull();
  });
});

describe('revenueTrend', () => {
  it('aligns the current period with the one before it, day by day, filling gaps with zero', () => {
    const rows = [sale('2026-11-19', '500'), sale('2026-11-19', '250'), sale('2026-11-17', '100')];
    const trend = revenueTrend(rows, TODAY, 3);
    expect(trend.days).toEqual(['2026-11-17', '2026-11-18', '2026-11-19']);
    expect(trend.current).toEqual([100, 0, 750]);
    expect(trend.previousDays).toEqual(['2026-11-14', '2026-11-15', '2026-11-16']);
    expect(trend.previous).toEqual([0, 0, 0]);
    expect(trend.currentTotal).toBe(850);
  });

  it('counts taxable value, so collected GST is not mistaken for income', () => {
    const row: DailySalesResponse = { ...sale('2026-11-19', '1000'), total_revenue: '1050' };
    expect(revenueTrend([row], TODAY, 1).currentTotal).toBe(1000);
  });
});

describe('drivers', () => {
  it('sums delivered stops per day across drivers', () => {
    const rows = [
      driverRow({ date: TODAY, driver_id: 'a', delivered_stops: 4 }),
      driverRow({ date: TODAY, driver_id: 'b', delivered_stops: 3 }),
      driverRow({ date: '2026-11-18', driver_id: 'a', delivered_stops: 9 }),
    ];
    expect(deliveredByDay(rows).get(TODAY)).toBe(7);
  });

  it("lists today's drivers busiest first, with what is still to do", () => {
    const rows = [
      driverRow({
        date: TODAY,
        driver_id: 'a',
        driver_name: 'Asha',
        total_stops: 5,
        delivered_stops: 3,
        failed_stops: 1,
      }),
      driverRow({
        date: TODAY,
        driver_id: 'b',
        driver_name: 'Bilal',
        total_stops: 9,
        delivered_stops: 9,
      }),
      driverRow({ date: '2026-11-18', driver_id: 'c', driver_name: 'Old', total_stops: 20 }),
    ];
    const today = driversToday(rows, TODAY);
    expect(today.map((d) => d.name)).toEqual(['Bilal', 'Asha']);
    expect(today[1]).toMatchObject({ delivered: 3, failed: 1, pending: 1, total: 5 });
  });

  it('never reports negative stops still to do', () => {
    const rows = [driverRow({ date: TODAY, total_stops: 2, delivered_stops: 2, failed_stops: 1 })];
    expect(driversToday(rows, TODAY)[0].pending).toBe(0);
  });
});

describe('pipeline, stock and cash', () => {
  it('puts the day in lifecycle order and counts missing stages as zero', () => {
    const stages = pipelineStages({
      bookings_today: 3,
      delivered_today: 5,
      failed_today: 1,
      pending_cancellations: 0,
      open_by_status: { confirmed: 2, out_for_delivery: 4 },
    });
    expect(stages.map((s) => s.key)).toEqual([
      'booked',
      'confirmed',
      'assigned',
      'ready_for_dispatch',
      'out_for_delivery',
      'delivered',
      'failed',
    ]);
    expect(stages.map((s) => s.count)).toEqual([0, 2, 0, 0, 4, 5, 1]);
  });

  it('orders stock by status and leaves out statuses with none', () => {
    const statuses = stockStatuses({ empty: 10, filled: 30, scrap: 0, damaged: 2 });
    expect(statuses.map((s) => s.key)).toEqual(['filled', 'empty', 'damaged']);
  });

  it('ranks cash by driver, largest first', () => {
    const cash = cashByDriver({
      total_cash: '300',
      drivers: [
        {
          driver_id: 'a',
          driver_name: 'A',
          cash_amount: '100',
          upi_amount: '0',
          oldest_route_date: TODAY,
          route_count: 1,
          stop_count: 1,
        },
        {
          driver_id: 'b',
          driver_name: 'B',
          cash_amount: '200',
          upi_amount: '50',
          oldest_route_date: TODAY,
          route_count: 1,
          stop_count: 1,
        },
      ],
    });
    expect(cash.map((d) => d.name)).toEqual(['B', 'A']);
    expect(cash[0].upi).toBe(50);
  });
});

describe('reorder bullets', () => {
  const signal = (
    type: string,
    onHand: number,
    point: number,
    safety: number,
  ): ReorderSignalResponse => ({
    cylinder_type_id: type,
    inventory_location_id: 'l',
    location_ref_id: 'r',
    on_hand: onHand,
    reorder_point: point,
    safety_stock: safety,
    policy_id: 'p',
    last_reorder_notified_at: null,
  });

  it('shows the emptiest location first, numbers repeats and flags those at safety stock', () => {
    const names = new Map([['t1', '14.2 kg']]);
    const bullets = reorderBullets([signal('t1', 90, 100, 50), signal('t1', 10, 100, 20)], names);
    expect(bullets.map((b) => b.label)).toEqual(['14.2 kg (2)', '14.2 kg']);
    expect(bullets[0].critical).toBe(true);
    expect(bullets[1].critical).toBe(false);
  });
});

describe('rating bands', () => {
  it('gives each band its share of the quarter, 5 stars first', () => {
    const bands = ratingBands({
      overall_stars: 4,
      total_orders: 200,
      quarter_start: '2026-10-01',
      quarter_end: '2027-01-01',
      distribution: [
        { stars: 4, order_count: 40 },
        { stars: 5, order_count: 160 },
      ],
    });
    expect(bands).toEqual([
      { stars: 5, orders: 160, share: 80 },
      { stars: 4, orders: 40, share: 20 },
    ]);
  });

  it('does not divide by zero before the first delivery', () => {
    const bands = ratingBands({
      overall_stars: null,
      total_orders: 0,
      quarter_start: '2026-10-01',
      quarter_end: '2027-01-01',
      distribution: [{ stars: 5, order_count: 0 }],
    });
    expect(bands[0].share).toBe(0);
  });
});

describe('refill bins', () => {
  it('has an overdue bin then one per day, and counts each customer once', () => {
    const item = (due: string) => ({
      branch_id: 'b',
      customer_id: due,
      full_name: 'C',
      interval_days: 30,
      last_delivered_at: '2026-10-20T00:00:00Z',
      phone_number: '1',
      refill_due_date: due,
    });
    const bins = refillBins(
      [item('2026-11-17'), item('2026-11-19'), item('2026-11-19'), item('2026-11-21')],
      TODAY,
      3,
    );
    expect(bins.map((b) => [b.label, b.count])).toEqual([
      ['Overdue', 1],
      ['19 Nov', 2],
      ['20 Nov', 0],
      ['21 Nov', 1],
    ]);
  });
});

describe('attention queue', () => {
  const money = (v: unknown) => `₹${v}`;

  it('is empty when nothing is waiting', () => {
    expect(attentionItems(ops(), money)).toEqual([]);
  });

  it('puts what is critical first, then warnings, biggest first, and skips zero counts', () => {
    const items = attentionItems(
      ops({
        open_complaints: 7,
        low_stock_count: 1,
        orders: {
          bookings_today: 0,
          delivered_today: 0,
          failed_today: 3,
          pending_cancellations: 2,
          open_by_status: { booked: 4 },
        },
      }),
      money,
    );
    expect(items.map((i) => i.key)).toEqual([
      'failed',
      'low-stock',
      'complaints',
      'cancellations',
      'booked',
    ]);
  });

  it('only includes invoice and cash rows the server sent', () => {
    const withMoney = attentionItems(
      ops({
        invoices: { on_hold_count: 2 } as OperationsSnapshotResponse['invoices'],
        cash: {
          handovers_awaiting_review: 1,
          awaiting_handover: '500',
        } as OperationsSnapshotResponse['cash'],
      }),
      money,
    );
    expect(withMoney.map((i) => i.key).sort()).toEqual(['handovers', 'on-hold']);
    expect(withMoney.find((i) => i.key === 'handovers')?.detail).toBe('₹500 still with drivers');
    expect(attentionItems(ops(), money)).toEqual([]);
  });
});
