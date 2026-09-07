import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { MessageService } from 'primeng/api';
import {
  AdminBranchService,
  AdminWarehouseService,
  type AppError,
  type BranchResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, FormFieldComponent } from '@lpg/shared/ui';

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
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, ReactiveFormsModule, ButtonDirective, ButtonIcon, ButtonLabel, InputText, DataGridComponent, FormFieldComponent, Select, Drawer, DrawerA11yDirective, IconField, InputIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Warehouses</h1>
          <p class="page-subtitle">Manage warehouse locations and branch assignments.</p>
        </div>
    </ng-template>
        <ng-template lpgHeaderPortal>
  <div class="page-header__actions">
            <button pButton (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Add Warehouse</span></button>
          </div>
</ng-template>
      </div>

      @if (warehouses().length > 0) {
      <div class="data-toolbar">
        <div class="data-toolbar__filters">
          <p-iconfield styleClass="w-full md:w-64">
            <p-inputicon styleClass="pi pi-search" />
            <input pInputText type="text" placeholder="Search warehouses..." class="w-full" />
          </p-iconfield>
        </div>
        <div class="data-toolbar__actions">
          <button pButton severity="secondary"><i pButtonIcon class="pi pi-file-excel"></i><span pButtonLabel>Export</span></button>
        </div>
      </div>
      }

      @if (!loading() && warehouses().length === 0) {
        <div class="empty-state">
          <i class="pi pi-building empty-state__icon"></i>
          <p class="empty-state__title">No warehouses found</p>
          <p class="empty-state__description">Get started by adding your first warehouse location.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Add Warehouse</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="warehouses()"
            [columns]="columns"
            [loading]="loading()"
            ariaLabel="Warehouses"
          />
        </section>
      }

      <!-- Create Warehouse Drawer -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Add a warehouse"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="addWarehouseForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <p class="page-lede">Create a new warehouse location and assign it to an operating branch.</p>
          
          <lpg-form-field label="Branch" for="warehouse-branch" [control]="form.controls.branchId" [messages]="{ required: 'Branch is required.' }">
            <p-select
              inputId="warehouse-branch"
              formControlName="branchId"
              [options]="branches()"
              optionLabel="name"
              optionValue="id"
              appendTo="body"
              [fluid]="true">
            </p-select>
          </lpg-form-field>

          <lpg-form-field label="Name" for="warehouse-name" [control]="form.controls.name" [messages]="{ required: 'Warehouse name is required.' }">
            <input pInputText id="warehouse-name" type="text" formControlName="name" placeholder="e.g. Northside Depot" [fluid]="true" />
          </lpg-form-field>

          <lpg-form-field label="Address" for="warehouse-address" [control]="form.controls.addressLine" [messages]="{ required: 'Address is required.' }">
            <input pInputText id="warehouse-address" type="text" formControlName="addressLine" placeholder="Full street address" [fluid]="true" />
          </lpg-form-field>
          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="createDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
              Save warehouse
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

    `,
  ],
})
export class WarehousesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly branchService = inject(AdminBranchService);
  private readonly messageService = inject(MessageService);

  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  
  protected readonly createDrawerVisible = signal(false);
  protected readonly submitting = signal(false);

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
  
  protected openCreateDrawer(): void {
    this.form.reset();
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
    const { branchId, name, addressLine } = this.form.getRawValue();

    this.warehouseService.createWarehouse(branchId, name, addressLine).subscribe({
      next: () => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `Warehouse "${name}" added.` });
        this.createDrawerVisible.set(false);
        this.form.reset();
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
