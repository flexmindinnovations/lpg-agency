import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { MessageService } from 'primeng/api';
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
 * Price list history + set-price drawer — `tenant:configure`.
 *
 * Historized, same as tenant configuration — an empty branch means a
 * tenant-wide default; a specific branch overrides it for that branch only.
 */
@Component({
  selector: 'lpg-price-list-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, ReactiveFormsModule, ButtonDirective, ButtonIcon, ButtonLabel, InputText, DataGridComponent, Select, Drawer, IconField, InputIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Pricing</h1>
          <p class="page-subtitle">Set and track cylinder prices by type, customer category, and branch.</p>
        </div>
    </ng-template>
        <ng-template lpgHeaderPortal>
  <div class="page-header__actions">
            <button pButton (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Set Price</span></button>
          </div>
</ng-template>
      </div>

      @if (prices().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
              <p-inputicon styleClass="pi pi-search" />
              <input pInputText type="text" placeholder="Search prices..." class="w-full" />
            </p-iconfield>
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary"><i pButtonIcon class="pi pi-file-excel"></i><span pButtonLabel>Export</span></button>
          </div>
        </div>
      }

      @if (!loading() && prices().length === 0) {
        <div class="empty-state">
          <i class="pi pi-tag empty-state__icon"></i>
          <p class="empty-state__title">No prices set</p>
          <p class="empty-state__description">Set the first price to get started.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Set Price</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <div class="grid-wrapper">
            <lpg-data-grid
              [rows]="prices()"
              [columns]="columns"
              [loading]="loading()"
              ariaLabel="Prices"
            />
          </div>
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
        <form id="setPriceForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <p class="page-lede">Set a price for a cylinder type and customer category. Leave branch empty for a tenant-wide default.</p>

          <div class="form-group">
            <label for="price-cylinder-type">Cylinder type</label>
            <p-select
              id="price-cylinder-type"
              formControlName="cylinderTypeId"
              [options]="cylinderTypes()"
              optionLabel="name"
              optionValue="id"
              placeholder="Select a cylinder type"
              styleClass="w-full"
              appendTo="body">
            </p-select>
            @if (form.controls.cylinderTypeId.touched && form.controls.cylinderTypeId.invalid) {
              <small class="field-error">Cylinder type is required.</small>
            }
          </div>

          <div class="form-group">
            <label for="price-customer-type">Customer type</label>
            <p-select
              id="price-customer-type"
              formControlName="customerType"
              [options]="customerTypes"
              placeholder="Select a customer type"
              styleClass="w-full"
              appendTo="body">
            </p-select>
            @if (form.controls.customerType.touched && form.controls.customerType.invalid) {
              <small class="field-error">Customer type is required.</small>
            }
          </div>

          <div class="form-group">
            <label for="price-branch">Branch (optional)</label>
            <p-select
              id="price-branch"
              formControlName="branchId"
              [options]="branches()"
              optionLabel="name"
              optionValue="id"
              placeholder="Tenant-wide default"
              [showClear]="true"
              styleClass="w-full"
              appendTo="body">
            </p-select>
          </div>

          <div class="form-group">
            <label for="price-value">Price</label>
            <input pInputText id="price-value" type="number" step="0.01" formControlName="price" placeholder="0.00" />
            @if (form.controls.price.touched && form.controls.price.invalid) {
              <small class="field-error">Price must be greater than 0.</small>
            }
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="createDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
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

      .grid-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-block-size: 0;
      }

      .grid-wrapper {
        flex: 1;
        min-block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }
    `,
  ],
})
export class PriceListPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly priceListService = inject(AdminPriceListService);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly branchService = inject(AdminBranchService);
  private readonly messageService = inject(MessageService);

  protected readonly prices = signal<PriceListEntryResponse[]>([]);
  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);
  protected readonly customerTypes = [...CUSTOMER_TYPES];

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
          this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Price saved.' });
          this.createDrawerVisible.set(false);
          this.form.reset({ price: 0 });
          this.reload();
        },
        error: (error: unknown) => {
          this.submitting.set(false);
          this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
        },
      });
  }
}
