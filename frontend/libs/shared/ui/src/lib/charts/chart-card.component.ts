import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TooltipModule } from 'primeng/tooltip';
import { EmptyStateComponent } from '../empty-state/empty-state.component';
import { SectionCardComponent } from '../section-card/section-card.component';
import { SkeletonComponent } from '../skeleton/skeleton.component';

export interface ChartCardLink {
  readonly label: string;
  readonly route: string;
}

export type ChartCardState = 'loading' | 'ready' | 'empty' | 'error';

/** The same numbers as the chart, as a table (the accessible way to read exact values). */
export interface ChartTable {
  readonly columns: readonly string[];
  readonly rows: readonly (readonly (string | number)[])[];
}

/**
 * A dashboard widget: heading, a chart (projected), and the states around it.
 * It keeps the chart's height in every state so the page does not shift while
 * data loads, and offers "View as table" so every value is reachable without
 * a pointer or colour vision.
 */
@Component({
  selector: 'lpg-chart-card',
  standalone: true,
  imports: [
    SectionCardComponent,
    SkeletonComponent,
    EmptyStateComponent,
    RouterLink,
    TooltipModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-section-card [heading]="heading()" [hasHeaderActions]="canShowTable() || !!link()">
      @if (link(); as l) {
        <a headerActions class="chart-card__toggle" [routerLink]="l.route">
          {{ l.label }}
          <i class="pi pi-arrow-right" aria-hidden="true"></i>
        </a>
      }
      @if (canShowTable()) {
        <button
          headerActions
          type="button"
          class="chart-card__icon-button"
          [attr.aria-label]="showTable() ? 'View as chart' : 'View as table'"
          [pTooltip]="showTable() ? 'View as chart' : 'View as table'"
          tooltipPosition="left"
          (click)="showTable.set(!showTable())"
        >
          <i class="pi" [class.pi-table]="!showTable()" [class.pi-chart-bar]="showTable()"></i>
        </button>
      }
      @if (subtitle()) {
        <p class="chart-card__subtitle" [pTooltip]="subtitle()" tooltipPosition="bottom">
          {{ subtitle() }}
        </p>
      }
      <div class="chart-card__body" [style.block-size.px]="height()">
        @switch (state()) {
          @case ('loading') {
            <lpg-skeleton variant="block" [height]="height() + 'px'" />
          }
          @case ('empty') {
            <lpg-empty-state
              [compact]="true"
              [title]="emptyTitle()"
              [description]="emptyDescription()"
            />
          }
          @case ('error') {
            <lpg-empty-state
              [compact]="true"
              tone="error"
              title="This could not be loaded"
              description="Your other widgets are unaffected. It will retry on the next refresh."
            />
          }
          @default {
            @if (showTable() && table(); as t) {
              <div
                class="chart-card__table-wrap"
                tabindex="0"
                role="region"
                [attr.aria-label]="heading() + ' data'"
              >
                <table class="chart-card__table">
                  <caption class="chart-card__sr">
                    {{
                      heading()
                    }}
                  </caption>
                  <thead>
                    <tr>
                      @for (c of t.columns; track $index) {
                        <th scope="col" [class.chart-card__num]="$index > 0">{{ c }}</th>
                      }
                    </tr>
                  </thead>
                  <tbody>
                    @for (row of t.rows; track $index) {
                      <tr>
                        @for (cell of row; track $index) {
                          <td [class.chart-card__num]="$index > 0">{{ cell }}</td>
                        }
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            } @else {
              <div [style.--lpg-chart-height.px]="height()">
                <ng-content />
              </div>
            }
          }
        }
      </div>
    </lpg-section-card>
  `,
  styles: [
    `
      :host {
        display: block;
        min-inline-size: 0;
        block-size: 100%;
      }

      lpg-section-card {
        block-size: 100%;
      }

      .chart-card__subtitle {
        margin: calc(-1 * var(--spacing-xs)) 0 0;
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        /* One line in every card, so all cards are the same height. The full
           text is in the tooltip. */
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .chart-card__toggle {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        padding: var(--spacing-xs) var(--spacing-sm);
        min-block-size: 24px;
        font: inherit;
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        background: transparent;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-full);
        cursor: pointer;
        text-decoration: none;
        transition: color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .chart-card__toggle {
        white-space: nowrap;
      }

      .chart-card__icon-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 28px;
        block-size: 28px;
        padding: 0;
        font-size: 12px;
        color: var(--color-text-secondary);
        background: transparent;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-full);
        cursor: pointer;
        transition: color var(--motion-duration-small) var(--motion-easing-standard);
      }

      .chart-card__icon-button:hover {
        color: var(--color-text-primary);
        border-color: var(--color-border-strong);
      }

      .chart-card__icon-button:focus-visible {
        outline: var(--component-focus-ring-width) solid var(--component-focus-ring-color);
        outline-offset: 2px;
      }

      .chart-card__toggle:hover {
        color: var(--color-text-primary);
        border-color: var(--color-border-strong);
      }

      .chart-card__toggle:focus-visible,
      .chart-card__table-wrap:focus-visible {
        outline: var(--component-focus-ring-width) solid var(--component-focus-ring-color);
        outline-offset: 2px;
      }

      /* Fixed to the chart's height in every state, so every card is the same
         height whatever it holds (a chart, a table, an empty message). */
      .chart-card__body {
        display: flex;
        flex-direction: column;
        justify-content: center;
        overflow: hidden;
      }

      .chart-card__table-wrap {
        overflow: auto;
        max-block-size: 100%;
      }

      .chart-card__table {
        inline-size: 100%;
        border-collapse: collapse;
        font-size: var(--typography-secondary-font-size);
        font-variant-numeric: tabular-nums;
      }

      .chart-card__table th,
      .chart-card__table td {
        padding: var(--spacing-xs) var(--spacing-sm);
        text-align: start;
        border-block-end: var(--border-width) solid var(--color-border-default);
      }

      .chart-card__table th {
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
      }

      .chart-card__num {
        text-align: end !important;
      }

      .chart-card__sr {
        position: absolute;
        inline-size: 1px;
        block-size: 1px;
        overflow: hidden;
        clip-path: inset(50%);
      }
    `,
  ],
})
export class ChartCardComponent {
  readonly heading = input.required<string>();
  readonly subtitle = input<string>('');
  /** Where "see all" goes (keyboard route to what a mark click opens). */
  readonly link = input<ChartCardLink | null>(null);
  readonly state = input<ChartCardState>('ready');
  /** Height of the chart area in px, kept in every state. */
  readonly height = input<number>(260);
  readonly table = input<ChartTable | null>(null);
  readonly emptyTitle = input<string>('Nothing to show yet');
  readonly emptyDescription = input<string>('');

  protected readonly showTable = signal(false);
  protected readonly canShowTable = computed(
    () => this.state() === 'ready' && this.table() !== null,
  );
}
