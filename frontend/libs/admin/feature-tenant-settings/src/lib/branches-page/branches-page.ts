import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { MessageService } from 'primeng/api';
import { AdminBranchService, type AppError, type BranchResponse } from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, FormFieldComponent } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the branch. Please try again.';
  }
}

/** Branch list + create drawer — `tenant:configure` (`permissionGuard`, route level). */
@Component({
  selector: 'lpg-branches-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, ReactiveFormsModule, ButtonDirective, ButtonIcon, ButtonLabel, InputText, DataGridComponent, FormFieldComponent, Drawer, DrawerA11yDirective, IconField, InputIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Branches</h1>
          <p class="page-subtitle">Manage branch locations and regional assignments.</p>
        </div>
    </ng-template>
      </div>

      @if (branches().length > 0) {
        <div class="data-toolbar">
          <div class="data-toolbar__filters">
            <p-iconfield styleClass="w-full md:w-64">
              <p-inputicon class="pi pi-search" />
              <input
                pInputText
                type="text"
                placeholder="Search branches..."
                class="w-full"
                [value]="searchQuery()"
                (input)="searchQuery.set($any($event.target).value)"
              />
            </p-iconfield>
          </div>
          <div class="data-toolbar__actions">
            <button pButton severity="secondary"><i pButtonIcon class="pi pi-file-excel"></i><span pButtonLabel>Export</span></button>
            <button pButton (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Add Branch</span></button>
          </div>
        </div>
      }

      @if (!loading() && branches().length === 0) {
        <div class="empty-state">
          <i class="pi pi-map-marker empty-state__icon"></i>
          <p class="empty-state__title">No branches found</p>
          <p class="empty-state__description">Get started by adding your first branch location.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Add Branch</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="branches()"
            [columns]="columns"
            [loading]="loading()"
            [searchQuery]="searchQuery()"
            ariaLabel="Branches"
          />
        </section>
      }

      <!-- Create Branch Drawer -->
      <p-drawer
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Add a branch"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="addBranchForm" [formGroup]="form" (ngSubmit)="submit()" novalidate class="dialog-form">
          <div class="dialog-form__fields">
          <p class="page-lede">Create a new branch and optionally assign it to a region.</p>

          <lpg-form-field label="Name" for="branch-name" [control]="form.controls.name" [messages]="{ required: 'Branch name is required.' }">
            <input pInputText id="branch-name" type="text" formControlName="name" placeholder="e.g. North City Branch" [fluid]="true" />
          </lpg-form-field>

          <lpg-form-field label="Region" for="branch-region" [control]="form.controls.region" hint="Optional.">
            <input pInputText id="branch-region" type="text" formControlName="region" placeholder="e.g. Northern Region" [fluid]="true" />
          </lpg-form-field>
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="createDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
              Save branch
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
export class BranchesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly branchService = inject(AdminBranchService);
  private readonly messageService = inject(MessageService);

  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  /** Filters `branches()` client-side (the full list is already loaded) via
   *  `lpg-data-grid`'s built-in quick filter — see its own `searchQuery`
   *  input docstring. */
  protected readonly searchQuery = signal('');
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);

  protected readonly columns: DataGridColumn<BranchResponse>[] = [
    { field: 'name', header: 'Name', sortable: true, filterable: true },
    { field: 'region', header: 'Region', sortable: true, filterable: true },
  ];

  protected readonly form = this.formBuilder.group({
    name: ['', [Validators.required]],
    region: [''],
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.branchService.listBranches().subscribe({
      next: (branches) => {
        this.branches.set(branches);
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
    const { name, region } = this.form.getRawValue();

    this.branchService.createBranch(name, region || null).subscribe({
      next: () => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `Branch "${name}" added.` });
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

