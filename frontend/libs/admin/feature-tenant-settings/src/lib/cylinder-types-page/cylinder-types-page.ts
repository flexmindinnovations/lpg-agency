import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
﻿import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { MessageService } from 'primeng/api';
import {
  AdminCylinderTypeService,
  type AppError,
  type CylinderTypeResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the cylinder type. Please try again.';
  }
}

/** Cylinder type list + create drawer â€” `tenant:configure`. */
@Component({
  selector: 'lpg-cylinder-types-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, ReactiveFormsModule, ButtonDirective, ButtonIcon, ButtonLabel, InputText, DataGridComponent, Drawer, IconField, InputIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Cylinder Types</h1>
          <p class="page-subtitle">Define LPG cylinder sizes and weights.</p>
        </div>
    </ng-template>
        <ng-template lpgHeaderPortal>
  <div class="page-header__actions">
            <button pButton (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Add Cylinder Type</span></button>
          </div>
</ng-template>
      </div>

      @if (cylinderTypes().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
              <p-inputicon styleClass="pi pi-search" />
              <input pInputText type="text" placeholder="Search cylinder types..." class="w-full" />
            </p-iconfield>
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary"><i pButtonIcon class="pi pi-file-excel"></i><span pButtonLabel>Export</span></button>
          </div>
        </div>
      }

      @if (!loading() && cylinderTypes().length === 0) {
        <div class="empty-state">
          <i class="pi pi-box empty-state__icon"></i>
          <p class="empty-state__title">No cylinder types found</p>
          <p class="empty-state__description">Get started by defining your first cylinder size.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Add Cylinder Type</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <div class="grid-wrapper">
            <lpg-data-grid
              [rows]="cylinderTypes()"
              [columns]="columns"
              [loading]="loading()"
              ariaLabel="Cylinder Types"
            />
          </div>
        </section>
      }

      <!-- Create Cylinder Type Drawer -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Add a cylinder type"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="addCylinderTypeForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <p class="page-lede">Define a new LPG cylinder type by name and weight.</p>

          <div class="form-group">
            <label for="cylinder-name">Name</label>
            <input pInputText id="cylinder-name" type="text" formControlName="name" placeholder="e.g. 14.2 kg Domestic" />
            @if (form.controls.name.touched && form.controls.name.invalid) {
              <small class="field-error">Cylinder type name is required.</small>
            }
          </div>

          <div class="form-group">
            <label for="cylinder-weight">Weight (kg)</label>
            <input
              pInputText
              id="cylinder-weight"
              type="number"
              step="0.01"
              formControlName="weightKg"
              placeholder="e.g. 14.2"
            />
            @if (form.controls.weightKg.touched && form.controls.weightKg.invalid) {
              <small class="field-error">Weight must be greater than 0.</small>
            }
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="createDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
              Save cylinder type
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
export class CylinderTypesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);
  private readonly messageService = inject(MessageService);

  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);

  protected readonly columns: DataGridColumn<CylinderTypeResponse>[] = [
    { field: 'name', header: 'Name', sortable: true, filterable: true },
    { field: 'weight_kg', header: 'Weight (kg)', sortable: true, numeric: true },
    { field: 'is_active', header: 'Active', sortable: true },
  ];

  protected readonly form = this.formBuilder.group({
    name: ['', [Validators.required]],
    weightKg: [0, [Validators.required, Validators.min(0.01)]],
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.cylinderTypeService.listCylinderTypes().subscribe({
      next: (cylinderTypes) => {
        this.cylinderTypes.set(cylinderTypes);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected openCreateDrawer(): void {
    this.form.reset({ weightKg: 0 });
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
    const { name, weightKg } = this.form.getRawValue();

    this.cylinderTypeService.createCylinderType(name, weightKg).subscribe({
      next: () => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `Cylinder type "${name}" added.` });
        this.createDrawerVisible.set(false);
        this.form.reset({ weightKg: 0 });
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
