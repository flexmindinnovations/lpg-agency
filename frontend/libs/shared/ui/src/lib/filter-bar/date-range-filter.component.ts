import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePicker } from 'primeng/datepicker';
import { DATE_INPUT_PLACEHOLDER, toIsoDate } from '@lpg/shared/util';

/** An inclusive date range as API `date` strings (`YYYY-MM-DD`). */
export interface DateRangeValue {
  readonly from: string | null;
  readonly to: string | null;
}

/** "2026-10-20" → that calendar day at local midnight (no UTC shift). */
function fromIsoDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const [y, m, d] = value.split('-').map(Number);
  return y && m && d ? new Date(y, m - 1, d) : null;
}

/**
 * The one date-range control for list filter bars: a single dd/mm/yyyy range
 * picker (pick the start, then the end) with Today/Clear buttons, the same
 * height as the other filter controls. Emits API `date` strings.
 */
@Component({
  selector: 'lpg-date-range-filter',
  standalone: true,
  imports: [FormsModule, DatePicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p-datepicker
      selectionMode="range"
      [ngModel]="range()"
      (ngModelChange)="onChange($event)"
      [placeholder]="placeholder()"
      [showIcon]="true"
      iconDisplay="input"
      [showButtonBar]="clearable()"
      [maxDate]="maxDate()"
      [readonlyInput]="true"
      [ariaLabel]="ariaLabel()"
      styleClass="lpg-date-range-filter"
    />
  `,
  styles: [
    `
      :host {
        display: inline-flex;
        inline-size: 15.5rem;
        max-inline-size: 100%;
      }
      :host ::ng-deep .lpg-date-range-filter {
        inline-size: 100%;
      }
    `,
  ],
})
export class DateRangeFilterComponent {
  readonly from = input<string | null>(null);
  readonly to = input<string | null>(null);
  readonly ariaLabel = input('Date range');
  /** Shows the Today/Clear bar; off where a range is always required. */
  readonly clearable = input(true);
  readonly maxDate = input<Date | null>(null);
  readonly placeholder = input(`${DATE_INPUT_PLACEHOLDER} – ${DATE_INPUT_PLACEHOLDER}`);
  readonly rangeChange = output<DateRangeValue>();

  protected readonly range = computed<Date[] | null>(() => {
    const start = fromIsoDate(this.from());
    if (!start) return null;
    const end = fromIsoDate(this.to());
    return end ? [start, end] : [start];
  });

  protected onChange(value: (Date | null)[] | null): void {
    const [start, end] = value ?? [];
    // A range is emitted once both ends are picked, or when it is cleared.
    if (start && !end) return;
    this.rangeChange.emit({ from: toIsoDate(start ?? null), to: toIsoDate(end ?? null) });
  }
}
