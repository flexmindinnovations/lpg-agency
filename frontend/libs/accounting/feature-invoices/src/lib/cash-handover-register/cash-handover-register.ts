import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { Select } from 'primeng/select';
import { Textarea } from 'primeng/textarea';
import { MessageService } from 'primeng/api';
import {
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  StatusChipCell,
  type ChipSeverity,
  formatCurrencyInr,
  formatReportDate,
  formatTimestamp,
  ExportButtonComponent,
  DateRangeFilterComponent,
  type DateRangeValue,
} from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  CashHandoverService,
  type CashHandoverRegisterEntryResponse,
} from '@lpg/shared/data-access';

const REVIEW_SEVERITY: Record<string, ChipSeverity> = {
  pending: 'warn',
  accepted: 'success',
  disputed: 'danger',
};

function istDate(offsetDays = 0): string {
  const date = new Date(Date.now() + offsetDays * 86_400_000);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(date);
}

/**
 * Cash handover register (DA-33): every driver's end-of-route cash
 * declaration with expected vs handed over, and the office's accept /
 * dispute decision. The person who declared a handover cannot verify it.
 */
@Component({
  selector: 'lpg-cash-handover-register',
  standalone: true,
  imports: [
    DateRangeFilterComponent,
    ExportButtonComponent,
    FormsModule,
    ButtonDirective,
    Drawer,
    Select,
    Textarea,
    DataGridComponent,
    EmptyStateComponent,
    HeaderTitlePortalDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './cash-handover-register.html',
  styleUrl: './cash-handover-register.css',
})
export class CashHandoverRegister implements OnInit {
  private readonly service = inject(CashHandoverService);
  private readonly messageService = inject(MessageService);
  private readonly grid = viewChild(DataGridComponent);

  protected readonly entries = signal<CashHandoverRegisterEntryResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly from = signal(istDate(-6));
  protected readonly to = signal(istDate());
  protected readonly status = signal<string | null>('pending');
  protected readonly selected = signal<CashHandoverRegisterEntryResponse | null>(null);
  protected readonly note = signal('');
  protected readonly submitting = signal(false);

  protected readonly statusOptions = [
    { label: 'To verify', value: 'pending' },
    { label: 'Accepted', value: 'accepted' },
    { label: 'Disputed', value: 'disputed' },
  ];

  protected readonly totals = computed(() =>
    this.entries().reduce(
      (sum, e) => ({
        expected: sum.expected + Number(e.expected_amount),
        actual: sum.actual + Number(e.actual_amount),
        shortfall: sum.shortfall + Number(e.shortfall),
      }),
      { expected: 0, actual: 0, shortfall: 0 },
    ),
  );

  protected readonly formatCurrencyInr = formatCurrencyInr;
  protected readonly formatTimestamp = formatTimestamp;

  protected readonly columns: DataGridColumn<CashHandoverRegisterEntryResponse>[] = [
    {
      field: 'handover_number',
      header: 'Handover #',
      onLinkClick: (row) => this.open(row),
      valueFormatter: (v) => (v as string | null) ?? 'Open',
    },
    { field: 'route_date', header: 'Route date', valueFormatter: formatReportDate },
    { field: 'driver_name', header: 'Driver', flex: 2 },
    {
      field: 'vehicle_registration',
      header: 'Vehicle',
      valueFormatter: (v) => (v as string | null) ?? '—',
    },
    { field: 'cash_stop_count', header: 'Cash stops', numeric: true },
    {
      field: 'expected_amount',
      header: 'Expected',
      numeric: true,
      valueFormatter: formatCurrencyInr,
    },
    {
      field: 'actual_amount',
      header: 'Handed over',
      numeric: true,
      valueFormatter: formatCurrencyInr,
    },
    {
      field: 'shortfall',
      header: 'Shortfall',
      numeric: true,
      valueFormatter: (v) => (Number(v) > 0 ? formatCurrencyInr(v) : '—'),
      cellClass: (v) => (Number(v) > 0 ? 'cell--danger' : ''),
    },
    {
      field: 'review_status',
      header: 'Status',
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: REVIEW_SEVERITY },
    },
  ];

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.service
      .listRegister({
        declaredFrom: this.from(),
        declaredTo: this.to(),
        reviewStatus: this.status(),
      })
      .subscribe({
        next: (entries) => {
          this.entries.set(entries);
          this.loading.set(false);
        },
        error: () => {
          this.error.set("The cash handover register couldn't be loaded.");
          this.loading.set(false);
        },
      });
  }

  protected setRange(range: DateRangeValue): void {
    if (!range.from || !range.to) return;
    this.from.set(range.from);
    this.to.set(range.to);
    this.load();
  }

  protected setStatus(value: string | null): void {
    this.status.set(value);
    this.load();
  }

  protected exportCsv(): void {
    this.grid()?.exportCsv(`cash-handovers-${this.from()}-to-${this.to()}`);
  }

  protected open(entry: CashHandoverRegisterEntryResponse): void {
    this.note.set('');
    this.selected.set(entry);
  }

  protected close(): void {
    this.selected.set(null);
  }

  /** Mirrors the server rule so the button explains itself: a dispute,
   * or accepting a short handover, needs a note. */
  protected noteRequired(outcome: 'accepted' | 'disputed'): boolean {
    const entry = this.selected();
    return outcome === 'disputed' || (!!entry && Number(entry.shortfall) > 0);
  }

  protected review(outcome: 'accepted' | 'disputed'): void {
    const entry = this.selected();
    if (!entry) return;
    if (this.noteRequired(outcome) && !this.note().trim()) {
      this.messageService.add({
        severity: 'warn',
        summary: 'Add a note',
        detail:
          outcome === 'disputed'
            ? 'Say what is wrong with this handover.'
            : 'Say how the shortfall was settled.',
      });
      return;
    }
    this.submitting.set(true);
    this.service.review(entry.id, outcome, this.note()).subscribe({
      next: () => {
        this.submitting.set(false);
        this.selected.set(null);
        this.messageService.add({
          severity: 'success',
          summary: outcome === 'accepted' ? 'Handover accepted' : 'Handover disputed',
          detail: `${entry.driver_name} · ${formatCurrencyInr(entry.actual_amount)}`,
        });
        this.load();
      },
      error: () => this.submitting.set(false),
    });
  }
}
