import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import {
  AdminBranchService,
  AdminCylinderTypeService,
  AdminPriceListService,
  type AppError,
  type BranchResponse,
  type CylinderTypeResponse,
  type PriceListEntryResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

const CUSTOMER_TYPES = ['domestic', 'commercial', 'industrial', 'government'] as const;

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the price. Please try again.';
  }
}

/**
 * Price list history + set-price form — `tenant:configure`.
 *
 * Historized, same as tenant configuration — an empty branch means a
 * tenant-wide default; a specific branch overrides it for that branch only.
 */
@Component({
  selector: 'lpg-price-list-page',
  standalone: true,
  imports: [ReactiveFormsModule, ButtonDirective, InputText, Message, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <h1>Price List</h1>

      <div class="admin-page__grid">
        <lpg-data-grid
          [rows]="prices()"
          [columns]="columns"
          [loading]="loading()"
          ariaLabel="Prices"
        />
      </div>

      <form class="admin-page__form" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <h2>Set a price</h2>
        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }
        <div class="admin-page__field">
          <label for="price-cylinder-type">Cylinder type</label>
          <select id="price-cylinder-type" formControlName="cylinderTypeId">
            <option value="" disabled>Select a cylinder type</option>
            @for (cylinderType of cylinderTypes(); track cylinderType.id) {
              <option [value]="cylinderType.id">{{ cylinderType.name }}</option>
            }
          </select>
        </div>
        <div class="admin-page__field">
          <label for="price-customer-type">Customer type</label>
          <select id="price-customer-type" formControlName="customerType">
            <option value="" disabled>Select a customer type</option>
            @for (customerType of customerTypes; track customerType) {
              <option [value]="customerType">{{ customerType }}</option>
            }
          </select>
        </div>
        <div class="admin-page__field">
          <label for="price-branch">Branch (optional — blank = tenant-wide default)</label>
          <select id="price-branch" formControlName="branchId">
            <option value="">Tenant-wide default</option>
            @for (branch of branches(); track branch.id) {
              <option [value]="branch.id">{{ branch.name }}</option>
            }
          </select>
        </div>
        <div class="admin-page__field">
          <label for="price-value">Price</label>
          <input pInputText id="price-value" type="number" step="0.01" formControlName="price" />
        </div>
        <button pButton type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Saving…' : 'Set price' }}
        </button>
      </form>
    </div>
  `,
  styles: [
    `
      .admin-page {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        padding: var(--spacing-lg);
      }

      .admin-page__grid {
        block-size: 400px;
      }

      .admin-page__form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        max-inline-size: 24rem;
      }

      .admin-page__field {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }
    `,
  ],
})
export class PriceListPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly priceListService = inject(AdminPriceListService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly branchService = inject(AdminBranchService);

  protected readonly prices = signal<PriceListEntryResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly customerTypes = CUSTOMER_TYPES;

  protected readonly columns: DataGridColumn<PriceListEntryResponse>[] = [
    { field: 'customer_type', header: 'Customer Type', sortable: true, filterable: true },
    { field: 'price', header: 'Price', sortable: true, numeric: true },
    { field: 'branch_id', header: 'Branch', filterable: true },
    { field: 'effective_from', header: 'Effective From', sortable: true },
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

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    const { cylinderTypeId, customerType, branchId, price } = this.form.getRawValue();

    this.priceListService
      .setPrice(cylinderTypeId, customerType, price, branchId || null)
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.form.reset({ price: 0 });
          this.reload();
        },
        error: (error: unknown) => {
          this.submitting.set(false);
          this.errorMessage.set(errorMessageFor(error));
        },
      });
  }
}
