import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { DatePicker } from 'primeng/datepicker';
import {
  EmptyStateComponent,
  PageActionsDirective,
  PageHeaderComponent,
  formatCurrencyInr,
} from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { CashHandoverService, type CashBookResponse } from '@lpg/shared/data-access';

const METHOD_LABELS: Record<string, string> = {
  cash: 'Cash',
  upi: 'UPI',
  card: 'Card',
  online_gateway: 'Online (Razorpay)',
  cheque: 'Cheque',
  bank_transfer: 'Bank transfer',
  credit: 'On credit',
};

function istToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date());
}

/** `YYYY-MM-DD` for a picked calendar day, without a UTC shift. */
function toIsoDay(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

/**
 * The daily cash book (ADR-066): what came in by mode, and what became of the
 * cash drivers handed over. Mirrors a shop's day-end cash sheet.
 */
@Component({
  selector: 'lpg-cash-book',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    ButtonDirective,
    DatePicker,
    EmptyStateComponent,
    HeaderTitlePortalDirective,
    PageActionsDirective,
    PageHeaderComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ng-template lpgHeaderTitlePortal>
      <lpg-page-header
        title="Cash book"
        subtitle="Money in by mode and the cash handed over, for one day."
      />
    </ng-template>
    <ng-template lpgPageActions>
      <a pButton routerLink="/cash-handovers" severity="secondary" [outlined]="true">
        <i class="pi pi-wallet"></i>
        <span>Handovers</span>
      </a>
    </ng-template>

    <div class="book">
      <div class="book__toolbar">
        <p-datepicker
          [ngModel]="pickedDate()"
          (ngModelChange)="setDay($event)"
          inputId="cash_book_date"
          iconDisplay="input"
          [showIcon]="true"
          [showOnFocus]="false"
          [maxDate]="today"
          ariaLabel="Cash book date"
          appendTo="body"
        />
      </div>

      @if (error(); as message) {
        <lpg-empty-state tone="error" title="Couldn't load the cash book" [description]="message" />
      } @else if (book(); as b) {
        <section class="book__section" aria-label="Collected today">
          <h2>Collected</h2>
          @if (b.collections.length === 0) {
            <p class="book__muted">No payments recorded on this day.</p>
          } @else {
            <ul class="book__rows">
              @for (c of b.collections; track c.method) {
                <li>
                  <span>{{ methodLabel(c.method) }}</span>
                  <span class="book__muted"
                    >{{ c.payment_count }}
                    {{ c.payment_count === 1 ? 'payment' : 'payments' }}</span
                  >
                  <span class="book__amount">{{ money(c.amount) }}</span>
                </li>
              }
              <li class="book__total">
                <span>Total collected</span>
                <span></span>
                <span class="book__amount">{{ money(b.total_collected) }}</span>
              </li>
            </ul>
          }
        </section>

        <section class="book__section" aria-label="Cash handed over">
          <h2>Cash handed over</h2>
          <dl class="book__grid">
            <div>
              <dt>Handovers</dt>
              <dd>{{ b.handover_count }}</dd>
            </div>
            <div>
              <dt>Expected</dt>
              <dd>{{ money(b.expected_total) }}</dd>
            </div>
            <div>
              <dt>Handed over</dt>
              <dd>{{ money(b.handed_over_total) }}</dd>
            </div>
            <div>
              <dt>Short</dt>
              <dd [class.book__danger]="+b.shortfall_total > 0">{{ money(b.shortfall_total) }}</dd>
            </div>
            <div>
              <dt>Excess</dt>
              <dd>{{ money(b.excess_total) }}</dd>
            </div>
          </dl>
        </section>

        <section class="book__section" aria-label="Verification">
          <h2>Verification</h2>
          <dl class="book__grid">
            <div>
              <dt>Accepted</dt>
              <dd>{{ money(b.accepted_total) }}</dd>
            </div>
            <div>
              <dt>Disputed</dt>
              <dd [class.book__danger]="+b.disputed_total > 0">{{ money(b.disputed_total) }}</dd>
            </div>
            <div>
              <dt>To verify</dt>
              <dd>
                {{ money(b.pending_total) }}
                <span class="book__muted">({{ b.pending_count }})</span>
              </dd>
            </div>
            <div>
              <dt>Still with drivers</dt>
              <dd>{{ money(b.cash_in_hand_total) }}</dd>
            </div>
          </dl>
        </section>
      } @else {
        <p class="book__muted" role="status">Loading…</p>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .book {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding-block-end: var(--spacing-xl);
      }
      .book__section {
        padding: var(--spacing-md);
        border: 1px solid var(--color-border-default);
        border-radius: var(--radius-md, 0.5rem);
        background: var(--color-surface-raised);
      }
      .book__section h2 {
        margin: 0 0 var(--spacing-sm);
        font-size: var(--typography-body-font-size);
        font-weight: var(--typography-label-font-weight);
      }
      .book__rows {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .book__rows li {
        display: grid;
        grid-template-columns: minmax(8rem, 1fr) auto auto;
        gap: var(--spacing-md);
        align-items: baseline;
      }
      .book__total {
        padding-block-start: var(--spacing-xs);
        border-block-start: 1px solid var(--color-border-default);
        font-weight: var(--typography-label-font-weight);
      }
      .book__amount {
        text-align: end;
        font-weight: var(--typography-label-font-weight);
      }
      .book__muted {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }
      .book__grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
        gap: var(--spacing-md);
        margin: 0;
      }
      .book__grid dt {
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }
      .book__grid dd {
        margin: 0;
        font-weight: var(--typography-label-font-weight);
      }
      .book__danger {
        color: var(--color-status-danger);
      }
    `,
  ],
})
export class CashBook implements OnInit {
  private readonly service = inject(CashHandoverService);

  protected readonly today = new Date();
  protected readonly day = signal(istToday());
  protected readonly book = signal<CashBookResponse | null>(null);
  protected readonly error = signal<string | null>(null);

  protected readonly pickedDate = computed(() => {
    const [y, m, d] = this.day().split('-').map(Number);
    return new Date(y, m - 1, d);
  });

  protected readonly money = formatCurrencyInr;

  ngOnInit(): void {
    this.load();
  }

  protected setDay(value: Date | null): void {
    if (!value) return;
    this.day.set(toIsoDay(value));
    this.load();
  }

  protected methodLabel(method: string): string {
    return METHOD_LABELS[method] ?? method;
  }

  private load(): void {
    this.book.set(null);
    this.error.set(null);
    this.service.cashBook(this.day()).subscribe({
      next: (book) => this.book.set(book),
      error: () => this.error.set('The cash book for this day could not be loaded.'),
    });
  }
}
