import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { ButtonDirective } from 'primeng/button';
import {
  AdminPriceListService,
  NotifyService,
  type CylinderTypeResponse,
  type PriceListProposalResponse,
} from '@lpg/shared/data-access';
import {
  SectionCardComponent,
  formatCurrencyInr,
  formatTimestamp,
  toSentenceCase,
} from '@lpg/shared/ui';

/**
 * Price changes fetched from the oil company, waiting for a decision.
 * Accepting one saves a price like any other. Nothing is shown when none wait.
 */
@Component({
  selector: 'lpg-rate-proposals-card',
  standalone: true,
  imports: [SectionCardComponent, ButtonDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (proposals().length > 0) {
      <lpg-section-card heading="New rates to review">
        <ul class="proposals">
          @for (p of proposals(); track p.id) {
            <li class="proposals__row">
              <div class="proposals__info">
                <span class="proposals__title">
                  {{ typeName(p.cylinder_type_id) }} · {{ sentenceCase(p.customer_type) }} ·
                  {{ money(p.proposed_price) }}
                </span>
                <span class="proposals__meta">
                  From {{ time(p.effective_from) }} ·
                  <a [href]="p.source_url" target="_blank" rel="noopener noreferrer">source</a>
                </span>
              </div>
              <div class="proposals__actions">
                <button
                  pButton
                  type="button"
                  severity="secondary"
                  [disabled]="reviewingId() === p.id"
                  (click)="review(p.id, 'reject')"
                >
                  Reject
                </button>
                <button
                  pButton
                  type="button"
                  [disabled]="reviewingId() === p.id"
                  (click)="review(p.id, 'accept')"
                >
                  @if (reviewingId() === p.id) {
                    <i class="pi pi-spin pi-spinner" aria-hidden="true"></i>
                  }
                  Accept
                </button>
              </div>
            </li>
          }
        </ul>
      </lpg-section-card>
    }
  `,
  styles: [
    `
      :host:not(:empty) {
        display: block;
        margin-block-end: var(--spacing-md);
      }

      .proposals {
        margin: 0;
        padding: 0;
        list-style: none;
      }

      /* Rows inside a card, divided by lines. */
      .proposals__row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
        padding-block: var(--spacing-sm);
        border-block-end: var(--border-width) solid var(--color-border-default);
      }

      .proposals__row:last-child {
        border-block-end: 0;
      }

      .proposals__info {
        display: flex;
        flex-direction: column;
        min-inline-size: 0;
      }

      .proposals__title {
        font-weight: var(--typography-label-font-weight);
      }

      .proposals__meta {
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }

      .proposals__meta a {
        color: var(--color-action-primary);
      }

      .proposals__actions {
        display: flex;
        gap: var(--spacing-sm);
      }
    `,
  ],
})
export class RateProposalsCard implements OnInit {
  readonly cylinderTypes = input<readonly CylinderTypeResponse[]>([]);
  /** A proposal was accepted, so the prices changed. */
  readonly accepted = output<void>();

  private readonly priceListService = inject(AdminPriceListService);
  private readonly notify = inject(NotifyService);

  protected readonly proposals = signal<PriceListProposalResponse[]>([]);
  protected readonly reviewingId = signal<string | null>(null);
  protected readonly money = formatCurrencyInr;
  protected readonly time = formatTimestamp;
  protected readonly sentenceCase = toSentenceCase;

  ngOnInit(): void {
    this.load();
  }

  protected typeName(id: string): string {
    return this.cylinderTypes().find((t) => t.id === id)?.name ?? 'Cylinder';
  }

  private load(): void {
    this.priceListService.listProposals().subscribe({
      next: (proposals) => this.proposals.set(proposals),
      // The global toast reports it; the card just stays hidden.
      error: () => this.proposals.set([]),
    });
  }

  protected review(proposalId: string, action: 'accept' | 'reject'): void {
    if (this.reviewingId()) return;
    this.reviewingId.set(proposalId);
    this.priceListService.reviewProposal(proposalId, action).subscribe({
      next: () => {
        this.reviewingId.set(null);
        this.notify.success(action === 'accept' ? 'New price saved.' : 'Rate rejected.');
        this.load();
        if (action === 'accept') this.accepted.emit();
      },
      error: () => this.reviewingId.set(null),
    });
  }
}
