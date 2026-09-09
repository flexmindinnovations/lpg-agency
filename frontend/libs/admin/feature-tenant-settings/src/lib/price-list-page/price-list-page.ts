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
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, FormFieldComponent, StatusChipCell, toSentenceCase, formatTimestamp } from '@lpg/shared/ui';

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
  imports: [HeaderTitlePortalDirective, ReactiveFormsModule, ButtonDirective, InputText, DataGridComponent, FormFieldComponent, Select, Drawer, DrawerA11yDirective, IconField, InputIcon],
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
      </div>

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
            <button pButton severity="secondary"><i class="pi pi-file-excel"></i><span>Export</span></button>
            <button pButton (click)="openCreateDrawer()"><i class="pi pi-plus"></i><span>Set Price</span></button>
          </div>
        </div>
      }

      @if (!loading() && prices().length === 0) {
        <div class="empty-state">
          <i class="pi pi-tag empty-state__icon"></i>
          <p class="empty-state__title">No prices set</p>
          <p class="empty-state__description">Set the first price to get started.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()"><i class="pi pi-plus"></i><span>Set Price</span></button>
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
        <form id="setPriceForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <div class="dialog-form__fields">
          <p class="page-lede">Set a price for a cylinder type and customer category. Leave branch empty for a tenant-wide default.</p>

          <lpg-form-field label="Cylinder type" for="price-cylinder-type" [control]="form.controls.cylinderTypeId" [messages]="{ required: 'Cylinder type is required.' }">
            <p-select
              inputId="price-cylinder-type"
              formControlName="cylinderTypeId"
              [options]="cylinderTypes()"
              optionLabel="name"
              optionValue="id"
              appendTo="body"
              [fluid]="true">
            </p-select>
          </lpg-form-field>

          <lpg-form-field label="Customer type" for="price-customer-type" [control]="form.controls.customerType" [messages]="{ required: 'Customer type is required.' }">
            <p-select
              inputId="price-customer-type"
              formControlName="customerType"
              [options]="customerTypes"
              optionLabel="label"
              optionValue="value"
              appendTo="body"
              [fluid]="true">
            </p-select>
          </lpg-form-field>

          <lpg-form-field label="Branch" for="price-branch" [control]="form.controls.branchId" hint="Leave empty for a tenant-wide default.">
            <p-select
              inputId="price-branch"
              formControlName="branchId"
              [options]="branches()"
              optionLabel="name"
              optionValue="id"
              placeholder="Tenant-wide default"
              [showClear]="true"
              appendTo="body"
              [fluid]="true">
            </p-select>
          </lpg-form-field>

          <lpg-form-field label="Price" for="price-value" [control]="form.controls.price" [messages]="{ required: 'Price is required.', min: 'Price must be greater than 0.' }">
            <input pInputText id="price-value" type="number" step="0.01" formControlName="price" placeholder="0.00" [fluid]="true" />
          </lpg-form-field>
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
  protected readonly customerTypes = CUSTOMER_TYPES.map((t) => ({ label: toSentenceCase(t), value: t }));

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
