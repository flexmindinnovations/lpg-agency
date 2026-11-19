import type { EChartsCoreOption } from 'echarts/core';
import type { ChartTable, ChartTheme } from '@lpg/shared/ui/charts';
import { formatCurrencyInr } from '@lpg/shared/ui';
import { shortDate } from './dashboard-dates';
import {
  compactInr,
  type DriverCash,
  type DriverToday,
  type PipelineStage,
  type RatingBand,
  type RefillBin,
  type ReorderBullet,
  type RevenueTrend,
  type StockStatus,
} from './dashboard-model';

/**
 * One builder per widget: data + theme in, a chart option, a sentence for
 * screen readers and the same numbers as a table out. Pure functions, so they
 * are tested without a canvas. Colours only ever come from the theme (design
 * tokens); marks carry value labels, so colour is never the only cue.
 */
export interface ChartSpec {
  readonly option: EChartsCoreOption;
  /** The chart's numbers in words. */
  readonly label: string;
  readonly table: ChartTable;
  readonly empty: boolean;
}

const ROUND = 4;

function tooltipBase(theme: ChartTheme) {
  return {
    confine: true,
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: theme.text, fontFamily: theme.fontFamily, fontSize: 12 },
  };
}

function base(theme: ChartTheme): EChartsCoreOption {
  return {
    animation: !theme.reducedMotion,
    animationDuration: 800,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 450,
    animationEasingUpdate: 'cubicInOut',
    textStyle: { color: theme.textMuted, fontFamily: theme.fontFamily, fontSize: 12 },
    tooltip: tooltipBase(theme),
  };
}

/** Tooltips are HTML strings, and names come from the API: escape them. */
function esc(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function valueAxis(theme: ChartTheme, formatter?: (v: number) => string): EChartsCoreOption {
  return {
    type: 'value',
    minInterval: 1,
    axisLabel: { color: theme.textMuted, formatter },
    splitLine: { lineStyle: { color: theme.border, type: 'dashed' } },
  };
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString('en-IN')} ${n === 1 ? one : many}`;
}

// ---- W03 Order pipeline ---------------------------------------------------

export function pipelineChart(stages: readonly PipelineStage[], theme: ChartTheme): ChartSpec {
  const colour = (s: PipelineStage) =>
    s.kind === 'done' ? theme.success : s.kind === 'failed' ? theme.danger : theme.primary;
  const total = stages.reduce((sum, s) => sum + s.count, 0);
  return {
    empty: total === 0,
    label: `Order pipeline: ${stages.map((s) => `${s.count} ${s.label.toLowerCase()}`).join(', ')}.`,
    table: {
      columns: ['Stage', 'Orders'],
      rows: stages.map((s) => [s.label, s.count]),
    },
    option: {
      ...base(theme),
      grid: { left: 8, right: 36, top: 8, bottom: 8, containLabel: true },
      tooltip: { ...tooltipBase(theme), trigger: 'axis', axisPointer: { type: 'none' } },
      xAxis: { ...valueAxis(theme), show: false },
      yAxis: {
        type: 'category',
        inverse: true,
        data: stages.map((s) => s.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: theme.text, margin: 12 },
      },
      series: [
        {
          type: 'bar',
          barWidth: 18,
          data: stages.map((s) => ({
            value: s.count,
            itemStyle: { color: colour(s), borderRadius: [0, ROUND, ROUND, 0] },
          })),
          label: { show: true, position: 'right', color: theme.text, fontWeight: 600 },
          showBackground: true,
          backgroundStyle: {
            color: theme.border,
            opacity: 0.35,
            borderRadius: [0, ROUND, ROUND, 0],
          },
          animationDelay: (index: number) => index * 70,
        },
      ],
    },
  };
}

// ---- W04 Drivers today ----------------------------------------------------

export function driversChart(drivers: readonly DriverToday[], theme: ChartTheme): ChartSpec {
  const part = (name: string, key: 'delivered' | 'failed' | 'pending', color: string) => ({
    name,
    type: 'bar',
    stack: 'stops',
    barWidth: 18,
    data: drivers.map((d) => d[key]),
    itemStyle: { color },
    label: {
      show: true,
      color: theme.surface,
      fontWeight: 600,
      formatter: (p: { value: number }) => (p.value > 0 ? String(p.value) : ''),
    },
    emphasis: { focus: 'series' },
    animationDelay: (index: number) => index * 70,
  });
  const delivered = drivers.reduce((s, d) => s + d.delivered, 0);
  const total = drivers.reduce((s, d) => s + d.total, 0);
  return {
    empty: drivers.length === 0,
    label: `Drivers today: ${delivered} of ${plural(total, 'stop')} delivered across ${plural(drivers.length, 'driver')}.`,
    table: {
      columns: ['Driver', 'Delivered', 'Failed', 'Still to do', 'Stops'],
      rows: drivers.map((d) => [d.name, d.delivered, d.failed, d.pending, d.total]),
    },
    option: {
      ...base(theme),
      grid: { left: 8, right: 16, top: 32, bottom: 8, containLabel: true },
      legend: {
        top: 0,
        left: 0,
        icon: 'roundRect',
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: theme.textMuted },
      },
      tooltip: { ...tooltipBase(theme), trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: valueAxis(theme),
      yAxis: {
        type: 'category',
        inverse: true,
        data: drivers.map((d) => d.name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: theme.text, margin: 12 },
      },
      series: [
        part('Delivered', 'delivered', theme.success),
        part('Failed', 'failed', theme.danger),
        part('Still to do', 'pending', theme.info),
      ],
    },
  };
}

// ---- W05 Cash on the road -------------------------------------------------

export function cashChart(drivers: readonly DriverCash[], theme: ChartTheme): ChartSpec {
  const total = drivers.reduce((s, d) => s + d.cash, 0);
  return {
    empty: drivers.length === 0 || total === 0,
    label: `Cash with drivers: ${compactInr(total)} across ${plural(drivers.length, 'driver')}.`,
    table: {
      columns: ['Driver', 'Cash', 'UPI', 'Routes', 'Oldest route'],
      rows: drivers.map((d) => [
        d.name,
        formatCurrencyInr(d.cash),
        formatCurrencyInr(d.upi),
        d.routes,
        shortDate(d.oldest.slice(0, 10)),
      ]),
    },
    option: {
      ...base(theme),
      grid: { left: 8, right: 64, top: 8, bottom: 8, containLabel: true },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'axis',
        axisPointer: { type: 'none' },
        formatter: (params: { dataIndex: number }[]) => {
          const d = drivers[params[0].dataIndex];
          return `<strong>${esc(d.name)}</strong><br/>Cash ${formatCurrencyInr(d.cash)}<br/>UPI ${formatCurrencyInr(d.upi)}<br/>${plural(d.routes, 'route')}, oldest ${shortDate(d.oldest.slice(0, 10))}`;
        },
      },
      xAxis: { ...valueAxis(theme), show: false },
      yAxis: {
        type: 'category',
        inverse: true,
        data: drivers.map((d) => d.name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: theme.text, margin: 12 },
      },
      series: [
        {
          type: 'bar',
          barWidth: 18,
          data: drivers.map((d) => d.cash),
          itemStyle: { color: theme.highlight, borderRadius: [0, ROUND, ROUND, 0] },
          label: {
            show: true,
            position: 'right',
            color: theme.text,
            fontWeight: 600,
            formatter: (p: { value: number }) => compactInr(p.value),
          },
          animationDelay: (index: number) => index * 70,
        },
      ],
    },
  };
}

// ---- W06 Revenue trend ----------------------------------------------------

export function revenueChart(trend: RevenueTrend, theme: ChartTheme): ChartSpec {
  const dates = trend.days.map(shortDate);
  return {
    empty: trend.currentTotal === 0 && trend.previousTotal === 0,
    label: `Revenue over the last ${trend.days.length} days: ${compactInr(trend.currentTotal)}, against ${compactInr(trend.previousTotal)} in the ${trend.days.length} days before.`,
    table: {
      columns: ['Date', 'Revenue', 'Same day, previous period'],
      rows: trend.days.map((day, i) => [
        shortDate(day),
        formatCurrencyInr(trend.current[i]),
        formatCurrencyInr(trend.previous[i]),
      ]),
    },
    option: {
      ...base(theme),
      grid: { left: 8, right: 16, top: 32, bottom: 8, containLabel: true },
      legend: {
        top: 0,
        left: 0,
        icon: 'roundRect',
        itemWidth: 14,
        itemHeight: 3,
        textStyle: { color: theme.textMuted },
      },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: theme.border } },
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0].dataIndex;
          return `<strong>${shortDate(trend.days[i])}</strong><br/>Revenue ${formatCurrencyInr(trend.current[i])}<br/><span style="opacity:.75">${shortDate(trend.previousDays[i])}: ${formatCurrencyInr(trend.previous[i])}</span>`;
        },
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLine: { lineStyle: { color: theme.border } },
        axisTick: { show: false },
        axisLabel: { color: theme.textMuted, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: theme.textMuted, formatter: (v: number) => compactInr(v) },
        splitLine: { lineStyle: { color: theme.border, type: 'dashed' } },
      },
      series: [
        {
          name: 'Previous period',
          type: 'line',
          data: trend.previous,
          symbol: 'none',
          smooth: 0.25,
          lineStyle: { color: theme.textMuted, width: 1.5, type: 'dashed' },
          itemStyle: { color: theme.textMuted },
        },
        {
          name: 'Revenue',
          type: 'line',
          data: trend.current,
          smooth: 0.25,
          showSymbol: false,
          symbolSize: 7,
          lineStyle: { color: theme.primary, width: 2.5 },
          itemStyle: { color: theme.primary },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: theme.primary },
                { offset: 1, color: 'transparent' },
              ],
            },
            opacity: 0.22,
          },
          emphasis: { focus: 'series' },
        },
      ],
    },
  };
}

// ---- W07 Stock by status --------------------------------------------------

export function stockChart(statuses: readonly StockStatus[], theme: ChartTheme): ChartSpec {
  const colours: Record<string, string> = {
    filled: theme.primary,
    empty: theme.textMuted,
    damaged: theme.danger,
    leakage: theme.warning,
    quarantine: theme.highlight,
    repair: theme.info,
    scrap: theme.border,
  };
  const total = statuses.reduce((s, x) => s + x.quantity, 0);
  return {
    empty: total === 0,
    label: `Cylinder stock: ${statuses.map((s) => `${s.quantity} ${s.label.toLowerCase()}`).join(', ')}.`,
    table: { columns: ['Status', 'Cylinders'], rows: statuses.map((s) => [s.label, s.quantity]) },
    option: {
      ...base(theme),
      grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
      tooltip: { ...tooltipBase(theme), trigger: 'axis', axisPointer: { type: 'none' } },
      xAxis: { ...valueAxis(theme), show: false },
      yAxis: {
        type: 'category',
        inverse: true,
        data: statuses.map((s) => s.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: theme.text, margin: 12 },
      },
      series: [
        {
          type: 'bar',
          barWidth: 16,
          data: statuses.map((s) => ({
            value: s.quantity,
            itemStyle: {
              color: colours[s.key] ?? theme.textMuted,
              borderRadius: [0, ROUND, ROUND, 0],
            },
          })),
          label: { show: true, position: 'right', color: theme.text, fontWeight: 600 },
          animationDelay: (index: number) => index * 70,
        },
      ],
    },
  };
}

// ---- W08 Reorder proximity (bullet) --------------------------------------

export function reorderChart(bullets: readonly ReorderBullet[], theme: ChartTheme): ChartSpec {
  const limit = (b: ReorderBullet) => Math.max(b.reorderPoint * 1.4, b.onHand, 1);
  return {
    empty: bullets.length === 0,
    label: `Stock close to reorder: ${bullets.map((b) => `${b.label} ${b.onHand} on hand, reorder at ${b.reorderPoint}`).join('; ')}.`,
    table: {
      columns: ['Cylinder', 'On hand', 'Reorder at', 'Safety stock'],
      rows: bullets.map((b) => [b.label, b.onHand, b.reorderPoint, b.safetyStock]),
    },
    option: {
      ...base(theme),
      grid: { left: 8, right: 24, top: 24, bottom: 8, containLabel: true },
      legend: {
        data: ['On hand', 'Reorder at'],
        top: 0,
        left: 0,
        icon: 'roundRect',
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: theme.textMuted },
      },
      tooltip: { ...tooltipBase(theme), trigger: 'axis', axisPointer: { type: 'none' } },
      xAxis: { ...valueAxis(theme), show: false },
      yAxis: {
        type: 'category',
        inverse: true,
        data: bullets.map((b) => b.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: theme.text, margin: 12 },
      },
      series: [
        {
          name: 'Range',
          type: 'bar',
          barWidth: 22,
          barGap: '-100%',
          silent: true,
          data: bullets.map(limit),
          itemStyle: { color: theme.border, opacity: 0.5, borderRadius: ROUND },
          tooltip: { show: false },
          legendHoverLink: false,
        },
        {
          name: 'On hand',
          type: 'bar',
          barWidth: 10,
          data: bullets.map((b) => ({
            value: b.onHand,
            itemStyle: { color: b.critical ? theme.danger : theme.warning, borderRadius: ROUND },
          })),
          label: { show: true, position: 'right', color: theme.text, fontWeight: 600 },
          z: 3,
          animationDelay: (index: number) => index * 70,
        },
        {
          name: 'Reorder at',
          type: 'pictorialBar',
          symbol: 'rect',
          symbolSize: [3, 24],
          symbolPosition: 'end',
          symbolOffset: [0, 0],
          data: bullets.map((b) => b.reorderPoint),
          itemStyle: { color: theme.text },
          z: 4,
        },
      ],
    },
  };
}

// ---- W09 Delivery-time rating --------------------------------------------

export function ratingChart(
  bands: readonly RatingBand[],
  stars: number | null,
  theme: ChartTheme,
): ChartSpec {
  const total = bands.reduce((s, b) => s + b.orders, 0);
  const colour = (n: number) => (n >= 4 ? theme.success : n === 3 ? theme.warning : theme.danger);
  return {
    empty: total === 0,
    label:
      stars === null
        ? `Delivery-time rating: not enough deliveries yet this quarter.`
        : `Delivery-time rating: ${stars} stars if the quarter ended now. ${bands.map((b) => `${b.share}% of orders in the ${b.stars}-star band`).join(', ')}.`,
    table: {
      columns: ['Band', 'Orders', 'Share'],
      rows: bands.map((b) => [`${b.stars} star`, b.orders, `${b.share}%`]),
    },
    option: {
      ...base(theme),
      grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'axis',
        axisPointer: { type: 'none' },
        formatter: (params: { dataIndex: number }[]) => {
          const b = bands[params[0].dataIndex];
          return `<strong>${b.stars} star band</strong><br/>${plural(b.orders, 'order')} (${b.share}%)`;
        },
      },
      xAxis: {
        type: 'category',
        data: bands.map((b) => `${b.stars} ★`),
        axisLine: { lineStyle: { color: theme.border } },
        axisTick: { show: false },
        axisLabel: { color: theme.text },
      },
      yAxis: { type: 'value', show: false, max: 100 },
      series: [
        {
          type: 'bar',
          barWidth: '55%',
          data: bands.map((b) => ({
            value: b.share,
            itemStyle: { color: colour(b.stars), borderRadius: [ROUND, ROUND, 0, 0] },
          })),
          label: {
            show: true,
            position: 'top',
            color: theme.text,
            fontWeight: 600,
            formatter: (p: { value: number }) => `${p.value}%`,
          },
          animationDelay: (index: number) => index * 90,
        },
      ],
    },
  };
}

// ---- W10 Refills due ------------------------------------------------------

export function refillsChart(bins: readonly RefillBin[], theme: ChartTheme): ChartSpec {
  const total = bins.reduce((s, b) => s + b.count, 0);
  const overdue = bins.find((b) => b.overdue)?.count ?? 0;
  return {
    empty: total === 0,
    label: `Refills due: ${plural(total, 'customer')} in the next ${bins.length - 1} days or overdue, ${overdue} overdue.`,
    table: { columns: ['Due', 'Customers'], rows: bins.map((b) => [b.label, b.count]) },
    option: {
      ...base(theme),
      grid: { left: 8, right: 8, top: 16, bottom: 8, containLabel: true },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: { dataIndex: number }[]) => {
          const b = bins[params[0].dataIndex];
          return `<strong>${b.label}</strong><br/>${plural(b.count, 'customer')} due`;
        },
      },
      xAxis: {
        type: 'category',
        data: bins.map((b) => b.label),
        axisLine: { lineStyle: { color: theme.border } },
        axisTick: { show: false },
        axisLabel: { color: theme.textMuted, interval: 0, rotate: 45, fontSize: 11 },
      },
      yAxis: valueAxis(theme),
      series: [
        {
          type: 'bar',
          barWidth: '60%',
          data: bins.map((b) => ({
            value: b.count,
            itemStyle: {
              color: b.overdue ? theme.danger : theme.primary,
              borderRadius: [ROUND, ROUND, 0, 0],
            },
          })),
          label: {
            show: true,
            position: 'top',
            color: theme.text,
            formatter: (p: { value: number }) => (p.value > 0 ? String(p.value) : ''),
          },
          animationDelay: (index: number) => index * 35,
        },
      ],
    },
  };
}
