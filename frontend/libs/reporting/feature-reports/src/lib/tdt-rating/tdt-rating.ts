import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Select } from 'primeng/select';
import {
  DataGridComponent,
  EmptyStateComponent,
  SectionCardComponent,
  StarRatingComponent,
  StatCardComponent,
  type DataGridColumn,
} from '@lpg/shared/ui';
import { TdtRatingService } from '@lpg/shared/data-access';
import type { TdtBandDistributionResponse } from '@lpg/shared/data-access';

interface QuarterOption {
  label: string;
  /** `'live'` for the current, still-open quarter; otherwise
   * `"<quarterStart>_<quarterEnd>"` (both `yyyy-mm-dd`, `quarterEnd`
   * exclusive) for a closed quarter. */
  value: string;
  quarterStart?: string;
  quarterEnd?: string;
}

const QUARTER_LABELS = ['Q1 (Jan–Mar)', 'Q2 (Apr–Jun)', 'Q3 (Jul–Sep)', 'Q4 (Oct–Dec)'];

/** `yyyy-mm-dd` for a UTC calendar date — the same string shape the backend's
 * `current_quarter_bounds` produces. */
function toIsoDate(year: number, month1: number, day: number): string {
  return `${year}-${String(month1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

/** Mirrors `application.compliance.queries.get_tdt_rating.current_quarter_
 * bounds` exactly — calendar quarters, `quarterEnd` exclusive. Used only to
 * build the closed-quarter picker options; the server is the source of
 * truth for what "current quarter" means when `'live'` is selected. */
function quarterBoundsFor(year: number, quarterIndex: number): { start: string; end: string } {
  const startMonth = quarterIndex * 3 + 1;
  const start = toIsoDate(year, startMonth, 1);
  const end =
    quarterIndex === 3 ? toIsoDate(year + 1, 1, 1) : toIsoDate(year, startMonth + 3, 1);
  return { start, end };
}

function buildQuarterOptions(today: Date): QuarterOption[] {
  const currentQuarterIndex = Math.floor(today.getMonth() / 3);
  const options: QuarterOption[] = [{ label: 'Live projection (current quarter)', value: 'live' }];

  let year = today.getFullYear();
  let quarterIndex = currentQuarterIndex;
  for (let i = 0; i < 4; i++) {
    quarterIndex -= 1;
    if (quarterIndex < 0) {
      quarterIndex = 3;
      year -= 1;
    }
    const { start, end } = quarterBoundsFor(year, quarterIndex);
    options.push({
      label: `${QUARTER_LABELS[quarterIndex]} ${year} (closed)`,
      value: `${start}_${end}`,
      quarterStart: start,
      quarterEnd: end,
    });
  }
  return options;
}

/**
 * TDT (Targeted Delivery Time) quarterly star rating — Phase 20 subsystem
 * 2. The one report tab with a user-facing period selector: switches
 * between the live, still-open quarter and the last four closed quarters.
 */
@Component({
  selector: 'lib-tdt-rating',
  standalone: true,
  imports: [
    FormsModule,
    Select,
    SectionCardComponent,
    StatCardComponent,
    StarRatingComponent,
    DataGridComponent,
    EmptyStateComponent,
  ],
  templateUrl: './tdt-rating.html',
  styleUrl: './tdt-rating.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TdtRating implements OnInit {
  private readonly tdtRatingService = inject(TdtRatingService);

  protected readonly quarterOptions = buildQuarterOptions(new Date());
  protected readonly selectedQuarter = signal<string>(this.quarterOptions[0].value);

  protected readonly overallStars = signal<number | null>(null);
  protected readonly totalOrders = signal(0);
  protected readonly distribution = signal<TdtBandDistributionResponse[]>([]);
  protected readonly periodLabel = signal('');
  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly isEmpty = computed(
    () => !this.loading() && !this.errorMessage() && this.totalOrders() === 0,
  );

  protected readonly columns: DataGridColumn<TdtBandDistributionResponse>[] = [
    {
      field: 'stars',
      header: 'Stars',
      width: 120,
      valueFormatter: (v) => `${v} ★`,
    },
    { field: 'order_count', header: 'Orders', numeric: true, width: 140 },
  ];

  ngOnInit(): void {
    this.load();
  }

  protected onQuarterChange(value: string): void {
    this.selectedQuarter.set(value);
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set(null);

    const selected = this.selectedQuarter();
    const option = this.quarterOptions.find((o) => o.value === selected);
    const request =
      selected === 'live' || !option?.quarterStart || !option?.quarterEnd
        ? this.tdtRatingService.getLiveProjection()
        : this.tdtRatingService.getQuarterlyRating({
            quarterStart: option.quarterStart,
            quarterEnd: option.quarterEnd,
          });

    request.subscribe({
      next: (rating) => {
        this.overallStars.set(rating.overall_stars);
        this.totalOrders.set(rating.total_orders);
        this.distribution.set(rating.distribution);
        this.periodLabel.set(`${rating.quarter_start} – ${rating.quarter_end}`);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set("Couldn't load the TDT rating for this period.");
        this.loading.set(false);
      },
    });
  }
}
