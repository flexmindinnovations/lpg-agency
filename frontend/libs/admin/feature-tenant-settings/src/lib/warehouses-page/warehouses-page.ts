import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import {
  AdminBranchService,
  AdminWarehouseService,
  type AppError,
  type BranchResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the warehouse. Please try again.';
  }
}

/** Warehouse list + create form — `tenant:configure`. */
@Component({
  selector: 'lpg-warehouses-page',
  standalone: true,
  imports: [ReactiveFormsModule, ButtonDirective, InputText, Message, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <h1>Warehouses</h1>

      <div class="admin-page__grid">
        <lpg-data-grid
          [rows]="warehouses()"
          [columns]="columns"
          [loading]="loading()"
          ariaLabel="Warehouses"
        />
      </div>

      <form class="admin-page__form" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <h2>Add a warehouse</h2>
        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }
        <div class="admin-page__field">
          <label for="warehouse-branch">Branch</label>
          <select id="warehouse-branch" formControlName="branchId">
            <option value="" disabled>Select a branch</option>
            @for (branch of branches(); track branch.id) {
              <option [value]="branch.id">{{ branch.name }}</option>
            }
          </select>
        </div>
        <div class="admin-page__field">
          <label for="warehouse-name">Name</label>
          <input pInputText id="warehouse-name" type="text" formControlName="name" />
        </div>
        <div class="admin-page__field">
          <label for="warehouse-address">Address</label>
          <input pInputText id="warehouse-address" type="text" formControlName="addressLine" />
        </div>
        <button pButton type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Saving…' : 'Add warehouse' }}
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
export class WarehousesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly branchService = inject(AdminBranchService);

  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly columns: DataGridColumn<WarehouseResponse>[] = [
    { field: 'name', header: 'Name', sortable: true, filterable: true },
    { field: 'address_line', header: 'Address', sortable: true, filterable: true },
  ];

  protected readonly form = this.formBuilder.group({
    branchId: ['', [Validators.required]],
    name: ['', [Validators.required]],
    addressLine: ['', [Validators.required]],
  });

  ngOnInit(): void {
    this.branchService.listBranches().subscribe((branches) => this.branches.set(branches));
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.warehouseService.listWarehouses().subscribe({
      next: (warehouses) => {
        this.warehouses.set(warehouses);
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
    const { branchId, name, addressLine } = this.form.getRawValue();

    this.warehouseService.createWarehouse(branchId, name, addressLine).subscribe({
      next: () => {
        this.submitting.set(false);
        this.form.reset();
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
