import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import * as echarts from 'echarts/core';
import type { EChartsCoreOption } from 'echarts/core';
import { BarChart, LineChart, PictorialBarChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import { ChartEntranceRegistry } from './chart-entrance.registry';

// Only what the dashboard draws, and the SVG renderer only: ECharts is
// tree-shaken to these, so it stays small and crisp when printed.
echarts.use([
  BarChart,
  LineChart,
  PictorialBarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  SVGRenderer,
]);

/**
 * Thin wrapper around one ECharts instance. The caller builds the option
 * (from design tokens, see `ChartThemeService`); this component only owns the
 * lifecycle: create, resize with its box, update in place, dispose.
 *
 * Updates call `setOption` without clearing, so a refresh morphs the existing
 * marks to the new values instead of redrawing from scratch, and an update
 * that changes nothing is skipped. With a `key`, the draw-in entrance plays
 * only the first time that chart is ever shown.
 */
@Component({
  selector: 'lpg-chart',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="chart" role="img" [attr.aria-label]="label()"></div>`,
  styles: [
    `
      :host {
        display: block;
        inline-size: 100%;
        block-size: var(--lpg-chart-height, 260px);
      }

      .chart {
        inline-size: 100%;
        block-size: 100%;
      }
    `,
  ],
})
export class ChartComponent {
  readonly option = input.required<EChartsCoreOption>();
  /** The chart's numbers in words (WCAG 1.1.1). */
  readonly label = input.required<string>();
  /** Identifies this chart across visits, so its entrance animation plays once. */
  readonly key = input<string | null>(null);
  /** Index of the mark (bar, point) the user clicked, for drill-through. */
  readonly markClick = output<number>();

  private readonly host = viewChild.required<ElementRef<HTMLElement>>('host');
  private readonly destroyRef = inject(DestroyRef);
  private readonly entrances = inject(ChartEntranceRegistry);
  private chart: echarts.ECharts | null = null;
  private signature = '';

  constructor() {
    afterNextRender(() => {
      const element = this.host().nativeElement;
      const chart = echarts.init(element, undefined, { renderer: 'svg' });
      this.chart = chart;
      const option = this.option();
      const key = this.key();
      const entrance = key === null || this.entrances.claim(key);
      this.signature = signatureOf(option);
      // A chart that has been shown before appears already drawn; whatever
      // changes after that still animates.
      chart.setOption(entrance ? option : { ...option, animation: false });
      chart.on('click', (event) => {
        if (typeof event.dataIndex === 'number') this.markClick.emit(event.dataIndex);
      });

      const resize = new ResizeObserver(() => chart.resize());
      resize.observe(element);
      this.destroyRef.onDestroy(() => {
        resize.disconnect();
        chart.dispose();
        this.chart = null;
      });
    });

    effect(() => {
      const option = this.option();
      const signature = signatureOf(option);
      // A refresh with the same numbers is not worth a redraw.
      if (!this.chart || signature === this.signature) return;
      this.signature = signature;
      this.chart.setOption(option);
    });
  }
}

/** Compact identity of an option's data and styling (functions are not part of it). */
function signatureOf(option: EChartsCoreOption): string {
  return JSON.stringify(option);
}
