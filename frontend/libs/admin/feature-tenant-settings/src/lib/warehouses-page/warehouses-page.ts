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
  AdminWarehouseService,
  NotifyService,
  type BranchResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, FormFieldComponent } from '@lpg/shared/ui';

/** AG Grid renders a boolean-valued column with its own checkbox cell by
 * default, ignoring `valueFormatter` (same fix as Cylinder Types' own
 * "Status" column) — this swaps that for plain "Active"/"Inactive" text. */
@Component({
  selector: 'lpg-warehouse-status-cell',
  standalone: true,
  template: `{{ label() }}`,
})
class WarehouseStatusCell {
  protected readonly label = signal('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid's ICellRendererParams
  agInit(params: any): void {
    this.label.set(params.value ? 'Active' : 'Inactive');
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  refresh(params: any): boolean {
    this.agInit(params);
    return true;
  }
}

/** Warehouse list + create form — `tenant:configure`. */
@Component({
  selector: 'lpg-warehouses-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, ReactiveFormsModule, ButtonDirective, InputText, DataGridComponent, FormFieldComponent, Select, Drawer, DrawerA11yDirective, IconField, InputIcon],
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
      </div>

      @if (warehouses().length > 0) {
      <div class="data-toolbar">
        <div class="data-toolbar__filters">
          <p-iconfield styleClass="w-full md:w-64">
            <p-inputicon class="pi pi-search" />
            <input
              pInputText
              type="text"
              placeholder="Search warehouses..."
              class="w-full"
              [value]="searchQuery()"
              (input)="searchQuery.set($any($event.target).value)"
            />
          </p-iconfield>
        </div>
        <div class="data-toolbar__actions">
          <button pButton severity="secondary"><i class="pi pi-file-excel"></i><span>Export</span></button>
          <button pButton (click)="openCreateDrawer()"><i class="pi pi-plus"></i><span>Add Warehouse</span></button>
        </div>
      </div>
      }

      @if (!loading() && warehouses().length === 0) {
        <div class="empty-state">
          <i class="pi pi-building empty-state__icon"></i>
          <p class="empty-state__title">No warehouses found</p>
          <p class="empty-state__description">Get started by adding your first warehouse location.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()"><i class="pi pi-plus"></i><span>Add Warehouse</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="warehouses()"
            [columns]="columns"
            [loading]="loading()"
            [searchQuery]="searchQuery()"
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
          <div class="dialog-form__fields">
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
          </div>
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

    `,
  ],
})
export class WarehousesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly branchService = inject(AdminBranchService);
  private readonly notify = inject(NotifyService);

  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');
  
  protected readonly createDrawerVisible = signal(false);
  protected readonly submitting = signal(false);

  protected readonly columns: DataGridColumn<WarehouseResponse>[] = [
    { field: 'name', header: 'Name', sortable: true, filterable: true },
    { field: 'address_line', header: 'Address', sortable: true, filterable: true },
    {
      field: 'is_active',
      header: 'Status',
      sortable: true,
      cellRenderer: WarehouseStatusCell,
    },
    {
      field: 'id',
      header: '',
      valueFormatter: (_value, row) => (row.is_active ? 'Deactivate' : 'Activate'),
      onLinkClick: (row) => this.toggleActive(row),
    },
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
        this.notify.success(`Warehouse "${name}" added.`);
        this.createDrawerVisible.set(false);
        this.form.reset();
        this.reload();
      },
      error: () => this.submitting.set(false),
    });
  }

  protected toggleActive(warehouse: WarehouseResponse): void {
    const nextActive = !warehouse.is_active;
    this.warehouseService.setActive(warehouse.id, nextActive).subscribe({
      next: () => {
        this.notify.success(`"${warehouse.name}" ${nextActive ? 'activated' : 'deactivated'}.`);
        this.reload();
      },
    });
  }
}
