import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { AdminBranchService } from '@lpg/shared/data-access';
import { ReportingStore, istDate, type ReportFilter } from '@lpg/reporting/data-access';

interface BranchOption {
  readonly label: string;
  readonly value: string;
}

/**
 * Date range, branch and export controls shared by the report tabs
 * (DA-12). The range lives in `ReportingStore`, so it survives switching
 * tabs; `apply` fires with the new filter whenever it changes.
 */
@Component({
  selector: 'lib-report-filters',
  standalone: true,
  imports: [FormsModule, ButtonDirective, InputText, Select],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="report-filters" role="group" aria-label="Report filters">
      <label class="report-filters__field">
        <span>From</span>
        <input
          pInputText
          type="date"
          [max]="store.filter().endDate"
          [value]="store.filter().startDate"
          (change)="update({ startDate: $any($event.target).value })"
        />
      </label>
      <label class="report-filters__field">
        <span>To</span>
        <input
          pInputText
          type="date"
          [min]="store.filter().startDate"
          [value]="store.filter().endDate"
          (change)="update({ endDate: $any($event.target).value })"
        />
      </label>
      <div class="report-filters__presets">
        <button
          pButton
          type="button"
          size="small"
          severity="secondary"
          [text]="true"
          (click)="preset(7)"
        >
          7 days
        </button>
        <button
          pButton
          type="button"
          size="small"
          severity="secondary"
          [text]="true"
          (click)="preset(30)"
        >
          30 days
        </button>
        <button
          pButton
          type="button"
          size="small"
          severity="secondary"
          [text]="true"
          (click)="thisMonth()"
        >
          This month
        </button>
      </div>
      @if (showBranch()) {
        <p-select
          [options]="branches()"
          [ngModel]="store.filter().branchId"
          (ngModelChange)="update({ branchId: $event })"
          optionLabel="label"
          optionValue="value"
          placeholder="All branches"
          [showClear]="true"
          ariaLabel="Branch"
        />
      }
      <span class="report-filters__spacer"></span>
      <button pButton type="button" severity="secondary" (click)="exportCsv.emit()">
        <i class="pi pi-file-excel"></i><span>Export CSV</span>
      </button>
    </div>
  `,
  styles: [
    `
      .report-filters {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm);
        margin-block-end: var(--spacing-md);
      }
      .report-filters__field {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }
      .report-filters__presets {
        display: inline-flex;
      }
      .report-filters__spacer {
        flex: 1;
      }
    `,
  ],
})
export class ReportFilters implements OnInit {
  protected readonly store = inject(ReportingStore);
  private readonly branchService = inject(AdminBranchService);

  readonly showBranch = input(true);
  readonly apply = output<ReportFilter>();
  readonly exportCsv = output<void>();

  protected readonly branches = signal<BranchOption[]>([]);

  ngOnInit(): void {
    if (this.showBranch()) {
      this.branchService.listBranches().subscribe({
        next: (branches) =>
          this.branches.set(branches.map((b) => ({ label: b.name, value: b.id }))),
        error: () => this.branches.set([]),
      });
    }
    this.apply.emit(this.store.filter());
  }

  protected update(change: Partial<ReportFilter>): void {
    this.store.setFilter(change);
    this.apply.emit(this.store.filter());
  }

  protected preset(days: number): void {
    this.update({ startDate: istDate(-(days - 1)), endDate: istDate() });
  }

  protected thisMonth(): void {
    const today = istDate();
    this.update({ startDate: `${today.slice(0, 8)}01`, endDate: today });
  }
}
