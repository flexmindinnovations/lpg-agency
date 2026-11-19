import type { ChartTheme } from '@lpg/shared/ui/charts';
import {
  cashChart,
  driversChart,
  pipelineChart,
  ratingChart,
  refillsChart,
  reorderChart,
  revenueChart,
  stockChart,
} from './chart-options';
import {
  pipelineStages,
  refillBins,
  revenueTrend,
  stockStatuses,
  type DriverCash,
  type DriverToday,
  type RatingBand,
  type ReorderBullet,
} from './dashboard-model';

const THEME: ChartTheme = {
  text: '#111',
  textMuted: '#555',
  border: '#ddd',
  surface: '#fff',
  primary: '#162b66',
  accent: '#55b9ee',
  highlight: '#ff6f12',
  success: '#16a34a',
  warning: '#d97706',
  danger: '#dc2626',
  info: '#2563eb',
  series: ['#162b66', '#ff6f12', '#55b9ee', '#555'],
  fontFamily: 'Inter, sans-serif',
  reducedMotion: false,
};

const ORDERS = {
  bookings_today: 0,
  delivered_today: 3,
  failed_today: 1,
  pending_cancellations: 0,
  open_by_status: { booked: 2 },
};

type Option = Record<string, unknown>;

describe('chart specs', () => {
  it('animate, unless the person prefers reduced motion', () => {
    const stages = pipelineStages(ORDERS);
    expect((pipelineChart(stages, THEME).option as Option)['animation']).toBe(true);
    expect(
      (pipelineChart(stages, { ...THEME, reducedMotion: true }).option as Option)['animation'],
    ).toBe(false);
  });

  it('take every colour from the theme', () => {
    const spec = pipelineChart(pipelineStages(ORDERS), THEME);
    const json = JSON.stringify(spec.option);
    expect(json).toContain(THEME.primary);
    expect(json).toContain(THEME.success);
    expect(json).toContain(THEME.danger);
  });

  it('describe the same numbers in words and in a table', () => {
    const spec = pipelineChart(pipelineStages(ORDERS), THEME);
    expect(spec.label).toContain('2 booked');
    expect(spec.label).toContain('3 delivered today');
    expect(spec.table.rows).toContainEqual(['Delivered today', 3]);
    expect(spec.empty).toBe(false);
  });

  it('say so when there is nothing to draw', () => {
    const none = pipelineStages({
      ...ORDERS,
      delivered_today: 0,
      failed_today: 0,
      open_by_status: {},
    });
    expect(pipelineChart(none, THEME).empty).toBe(true);
    expect(driversChart([], THEME).empty).toBe(true);
    expect(cashChart([], THEME).empty).toBe(true);
    expect(stockChart([], THEME).empty).toBe(true);
    expect(reorderChart([], THEME).empty).toBe(true);
    expect(refillsChart(refillBins([], '2026-11-19', 3), THEME).empty).toBe(true);
  });

  it('drivers: stack delivered, failed and still-to-do per driver', () => {
    const drivers: DriverToday[] = [
      { name: 'Asha', delivered: 4, failed: 1, pending: 2, total: 7 },
    ];
    const spec = driversChart(drivers, THEME);
    const series = (spec.option as { series: { name: string; data: number[] }[] }).series;
    expect(series.map((s) => s.name)).toEqual(['Delivered', 'Failed', 'Still to do']);
    expect(series.map((s) => s.data[0])).toEqual([4, 1, 2]);
    expect(spec.label).toContain('4 of 7 stops delivered');
  });

  it('cash: escapes driver names in the tooltip (names come from the API)', () => {
    const cash: DriverCash[] = [
      { name: '<img src=x onerror=alert(1)>', cash: 500, upi: 0, routes: 1, oldest: '2026-11-19' },
    ];
    const tooltip = (
      cashChart(cash, THEME).option as {
        tooltip: { formatter: (p: { dataIndex: number }[]) => string };
      }
    ).tooltip;
    const html = tooltip.formatter([{ dataIndex: 0 }]);
    expect(html).not.toContain('<img');
    expect(html).toContain('&#60;img');
  });

  it('revenue: draws this period and a dashed previous one, with both in the table', () => {
    const trend = revenueTrend(
      [
        {
          branch_id: 'b',
          sale_date: '2026-11-19',
          taxable_value: '900',
          total_invoices: 1,
          total_revenue: '900',
          total_tax: '0',
        },
      ],
      '2026-11-19',
      2,
    );
    const spec = revenueChart(trend, THEME);
    const series = (spec.option as { series: { name: string; lineStyle: { type?: string } }[] })
      .series;
    expect(series.map((s) => s.name)).toEqual(['Previous period', 'Revenue']);
    expect(series[0].lineStyle.type).toBe('dashed');
    expect(spec.table.columns).toContain('Same day, previous period');
    expect(spec.empty).toBe(false);
  });

  it('stock: colours damaged and leakage as problems, filled as the main series', () => {
    const spec = stockChart(stockStatuses({ filled: 10, damaged: 2 }), THEME);
    const data = (spec.option as { series: { data: { itemStyle: { color: string } }[] }[] })
      .series[0].data;
    expect(data[0].itemStyle.color).toBe(THEME.primary);
    expect(data[1].itemStyle.color).toBe(THEME.danger);
  });

  it('reorder: marks the reorder point and turns red at safety stock', () => {
    const bullets: ReorderBullet[] = [
      { label: '19 kg', onHand: 5, reorderPoint: 40, safetyStock: 10, critical: true },
    ];
    const series = (
      reorderChart(bullets, THEME).option as {
        series: { type: string; data: unknown[] }[];
      }
    ).series;
    expect(series.map((s) => s.type)).toEqual(['bar', 'bar', 'pictorialBar']);
    expect(series[2].data).toEqual([40]);
    expect(JSON.stringify(series[1].data)).toContain(THEME.danger);
  });

  it('rating: says when there is not enough data for stars', () => {
    const bands: RatingBand[] = [{ stars: 5, orders: 0, share: 0 }];
    expect(ratingChart(bands, null, THEME).label).toContain('not enough deliveries');
    expect(ratingChart([{ stars: 5, orders: 9, share: 100 }], 5, THEME).label).toContain('5 stars');
  });

  it('refills: draws overdue in the danger colour', () => {
    const bins = refillBins(
      [
        {
          branch_id: 'b',
          customer_id: 'c',
          full_name: 'C',
          interval_days: 30,
          last_delivered_at: '',
          phone_number: '1',
          refill_due_date: '2026-11-10',
        },
      ],
      '2026-11-19',
      2,
    );
    const data = (
      refillsChart(bins, THEME).option as {
        series: { data: { itemStyle: { color: string } }[] }[];
      }
    ).series[0].data;
    expect(data[0].itemStyle.color).toBe(THEME.danger);
    expect(data[1].itemStyle.color).toBe(THEME.primary);
  });
});
