import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import {
  AdminBranchService,
  AdminCylinderTypeService,
  AdminPriceListService,
  NotifyService,
  type BranchResponse,
  type CylinderTypeResponse,
  type PriceListEntryResponse,
  type PriceListProposalResponse,
} from '@lpg/shared/data-access';
import {
  DataGridComponent,
  type DataGridColumn,
  FormFieldComponent,
  SectionCardComponent,
  StatusChipCell,
  toSentenceCase,
  formatTimestamp,
} from '@lpg/shared/ui';

const CUSTOMER_TYPES = ['domestic', 'commercial', 'industrial', 'government'] as const;

/**
 * Price list history + set-price drawer — `tenant:configure`.
 *
 * Historized, same as tenant configuration — an empty branch means a
 * tenant-wide default; a specific branch overrides it for that branch only.
 */
@Component({
  selector: 'lpg-price-list-page',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    DataGridComponent,
    FormFieldComponent,
    SectionCardComponent,
    Select,
    Drawer,
    DrawerA11yDirective,
    IconField,
    InputIcon,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <div class="page-header__text">
            <h1 class="page-title">Pricing</h1>
            <p class="page-subtitle">
              Set and track cylinder prices by type, customer category, and branch.
            </p>
          </div>
        </ng-template>
      </div>

      <!-- Pending Rate Proposals — AI Operational Intelligence, Horizon 1
           Stage 3. Heuristic-fetched (or manually staged) proposals
           awaiting review; accepting one writes a real price below through
           the same append-only path "Set Price" uses. Hidden when there's
           nothing pending, same as every other empty section on this page. -->
      @if (proposals().length > 0) {
        <lpg-section-card heading="Pending Rate Proposals">
          <div class="proposal-list">
            @for (p of proposals(); track p.id) {
              <div class="proposal-row">
                <div class="proposal-row__info">
                  <span class="proposal-row__title">
                    {{ cylinderTypeName(p.cylinder_type_id) }} ·
                    {{ toSentenceCase(p.customer_type) }}
                  </span>
                  <span class="proposal-row__meta">
                    ₹{{ p.proposed_price }} effective {{ formatTimestamp(p.effective_from) }} ·
                    <a [href]="p.source_url" target="_blank" rel="noopener noreferrer">source</a>
                  </span>
                </div>
                <div class="proposal-row__actions">
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
                      <i class="pi pi-spin pi-spinner"></i>
                    }
                    Accept
                  </button>
                </div>
              </div>
            }
          </div>
        </lpg-section-card>
      }

      @if (prices().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
              <p-inputicon class="pi pi-search" />
              <input
                pInputText
                type="text"
                placeholder="Search prices..."
                class="w-full"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </p-iconfield>
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary">
              <i class="pi pi-file-excel"></i><span>Export</span>
            </button>
            <button pButton (click)="openCreateDrawer()">
              <i class="pi pi-plus"></i><span>Set Price</span>
            </button>
          </div>
        </div>
      }

      @if (!loading() && prices().length === 0) {
        <div class="empty-state">
          <i class="pi pi-tag empty-state__icon"></i>
          <p class="empty-state__title">No prices set</p>
          <p class="empty-state__description">Set the first price to get started.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Set Price</span>
          </button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="prices()"
            [columns]="columns"
            [loading]="loading()"
            [searchQuery]="searchQuery()"
            ariaLabel="Prices"
          />
        </section>
      }

      <!-- Set Price Drawer -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Set a price"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form
          id="setPriceForm"
          [formGroup]="form"
          (ngSubmit)="submit()"
          novalidate
          class="dialog-form"
        >
          <div class="dialog-form__fields">
            <p class="page-lede">
              Set a price for a cylinder type and customer category. Leave branch empty for a
              tenant-wide default.
            </p>

            <lpg-form-field
              label="Cylinder type"
              for="price-cylinder-type"
              [control]="form.controls.cylinderTypeId"
              [messages]="{ required: 'Cylinder type is required.' }"
            >
              <p-select
                inputId="price-cylinder-type"
                formControlName="cylinderTypeId"
                [options]="cylinderTypes()"
                optionLabel="name"
                optionValue="id"
                appendTo="body"
                [fluid]="true"
              >
              </p-select>
            </lpg-form-field>

            <lpg-form-field
              label="Customer type"
              for="price-customer-type"
              [control]="form.controls.customerType"
              [messages]="{ required: 'Customer type is required.' }"
            >
              <p-select
                inputId="price-customer-type"
                formControlName="customerType"
                [options]="customerTypes"
                optionLabel="label"
                optionValue="value"
                appendTo="body"
                [fluid]="true"
              >
              </p-select>
            </lpg-form-field>

            <lpg-form-field
              label="Branch"
              for="price-branch"
              [control]="form.controls.branchId"
              hint="Leave empty for a tenant-wide default."
            >
              <p-select
                inputId="price-branch"
                formControlName="branchId"
                [options]="branches()"
                optionLabel="name"
                optionValue="id"
                placeholder="Tenant-wide default"
                [showClear]="true"
                appendTo="body"
                [fluid]="true"
              >
              </p-select>
            </lpg-form-field>

            <lpg-form-field
              label="Price"
              for="price-value"
              [control]="form.controls.price"
              [messages]="{ required: 'Price is required.', min: 'Price must be greater than 0.' }"
            >
              <input
                pInputText
                id="price-value"
                type="number"
                step="0.01"
                formControlName="price"
                placeholder="0.00"
                [fluid]="true"
              />
            </lpg-form-field>
          </div>

          <div class="modal-actions">
            <button
              pButton
              type="button"
              severity="secondary"
              (click)="createDrawerVisible.set(false)"
            >
              Cancel
            </button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid">
              @if (submitting()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
              Save price
            </button>
          </div>
        </form>
      </p-drawer>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        block-size: 100%;
      }

      .admin-page {
        display: flex;
        flex-direction: column;
        block-size: 100%;
      }

      .proposal-list {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
      }

      .proposal-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-md);
        background: var(--color-surface-overlay);
        border-radius: var(--radius-input);
        flex-wrap: wrap;
      }

      .proposal-row__info {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-inline-size: 0;
      }

      .proposal-row__title {
        font-weight: 600;
        color: var(--color-text-primary);
      }

      .proposal-row__meta {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .proposal-row__meta a {
        color: var(--color-action-primary);
      }

      .proposal-row__actions {
        display: flex;
        gap: var(--spacing-sm);
        flex-shrink: 0;
      }
    `,
  ],
})
export class PriceListPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly priceListService = inject(AdminPriceListService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly branchService = inject(AdminBranchService);
  private readonly notify = inject(NotifyService);

  protected readonly prices = signal<PriceListEntryResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly searchQuery = signal('');
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);
  protected readonly customerTypes = CUSTOMER_TYPES.map((t) => ({
    label: toSentenceCase(t),
    value: t,
  }));
  protected readonly toSentenceCase = toSentenceCase;
  protected readonly formatTimestamp = formatTimestamp;

  protected readonly proposals = signal<PriceListProposalResponse[]>([]);
  protected readonly reviewingId = signal<string | null>(null);

  protected readonly columns: DataGridColumn<PriceListEntryResponse>[] = [
    {
      field: 'customer_type',
      header: 'Customer Type',
      sortable: true,
      filterable: true,
      cellRenderer: StatusChipCell,
    },
    { field: 'price', header: 'Price', sortable: true, numeric: true },
    { field: 'branch_id', header: 'Branch', filterable: true },
    {
      field: 'effective_from',
      header: 'Effective From',
      sortable: true,
      valueFormatter: (value) => formatTimestamp(value),
    },
  ];

  protected readonly form = this.formBuilder.group({
    cylinderTypeId: ['', [Validators.required]],
    customerType: ['', [Validators.required]],
    branchId: [''],
    price: [0, [Validators.required, Validators.min(0.01)]],
  });

  ngOnInit(): void {
    this.cylinderTypeService
      .listCylinderTypes()
      .subscribe((types) => this.cylinderTypes.set(types));
    this.branchService.listBranches().subscribe((branches) => this.branches.set(branches));
    this.reload();
    this.loadProposals();
  }

  protected cylinderTypeName(cylinderTypeId: string): string {
    return this.cylinderTypes().find((t) => t.id === cylinderTypeId)?.name ?? cylinderTypeId;
  }

  private loadProposals(): void {
    this.priceListService.listProposals().subscribe({
      next: (proposals) => this.proposals.set(proposals),
      // Error toast is handled globally by globalErrorToastInterceptor —
      // an empty pending-proposals panel on failure is a reasonable
      // degrade, not a blocking one.
      error: () => this.proposals.set([]),
    });
  }

  protected review(proposalId: string, action: 'accept' | 'reject'): void {
    if (this.reviewingId()) {
      return;
    }
    this.reviewingId.set(proposalId);
    this.priceListService.reviewProposal(proposalId, action).subscribe({
      next: () => {
        this.reviewingId.set(null);
        this.notify.success(
          action === 'accept' ? 'Proposal accepted — price saved.' : 'Proposal rejected.',
        );
        this.loadProposals();
        if (action === 'accept') {
          this.reload();
        }
      },
      error: () => this.reviewingId.set(null),
    });
  }

  private reload(): void {
    this.loading.set(true);
    this.priceListService.listPrices().subscribe({
      next: (prices) => {
        this.prices.set(prices);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected openCreateDrawer(): void {
    this.form.reset({ price: 0 });
    this.createDrawerVisible.set(true);
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    const { cylinderTypeId, customerType, branchId, price } = this.form.getRawValue();

    this.priceListService
      .setPrice(cylinderTypeId, customerType, price, branchId || null)
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.notify.success('Price saved.');
          this.createDrawerVisible.set(false);
          this.form.reset({ price: 0 });
          this.reload();
        },
        error: () => this.submitting.set(false),
      });
  }
}
