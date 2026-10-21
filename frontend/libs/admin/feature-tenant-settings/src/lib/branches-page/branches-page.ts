import { notBlank } from '@lpg/shared/util';
import { ConfirmationService } from 'primeng/api';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import {
  AdminBranchService,
  NotifyService,
  type BranchResponse,
  errorMessageFor,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, FormFieldComponent } from '@lpg/shared/ui';

/** AG Grid renders a boolean-valued column with its own checkbox cell by
 * default, ignoring `valueFormatter` (same fix as Cylinder Types' own
 * "Status" column) — this swaps that for plain "Active"/"Inactive" text. */
@Component({
  selector: 'lpg-branch-status-cell',
  standalone: true,
  template: `{{ label() }}`,
})
class BranchStatusCell {
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

/** Branch list + create drawer — `tenant:configure` (`permissionGuard`, route level). */
@Component({
  selector: 'lpg-branches-page',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    DataGridComponent,
    FormFieldComponent,
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
            <button pButton severity="secondary" type="button" (click)="exportCsv()">
              <i class="pi pi-file-excel"></i><span>Export CSV</span>
            </button>
            <button pButton (click)="openCreateDrawer()">
              <i class="pi pi-plus"></i><span>Add Branch</span>
            </button>
          </div>
        </div>
      }

      @if (!loading() && !loadError() && branches().length === 0) {
        <div class="empty-state">
          <i class="pi pi-map-marker empty-state__icon"></i>
          <p class="empty-state__title">No branches found</p>
          <p class="empty-state__description">Get started by adding your first branch location.</p>
          <button pButton class="mt-4" (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Add Branch</span>
          </button>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="branches()"
            [columns]="columns"
            [loading]="loading()"
            [error]="loadError()"
            (retry)="reload()"
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
        <form
          id="addBranchForm"
          [formGroup]="form"
          (ngSubmit)="submit()"
          novalidate
          class="dialog-form"
        >
          <div class="dialog-form__fields">
            <p class="page-lede">Create a new branch and optionally assign it to a region.</p>

            <lpg-form-field
              label="Name"
              for="branch-name"
              [control]="form.controls.name"
              [messages]="{ required: 'Branch name is required.' }"
            >
              <input
                pInputText
                id="branch-name"
                type="text"
                formControlName="name"
                placeholder="e.g. North City Branch"
                [fluid]="true"
              />
            </lpg-form-field>

            <lpg-form-field
              label="Region"
              for="branch-region"
              [control]="form.controls.region"
              [optional]="true"
            >
              <input
                pInputText
                id="branch-region"
                type="text"
                formControlName="region"
                placeholder="e.g. Northern Region"
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
            <button pButton type="submit" [disabled]="submitting()">
              @if (submitting()) {
                <i class="pi pi-spin pi-spinner"></i>
              }
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
  private readonly grid = viewChild(DataGridComponent);

  /** DA-14: the grid as shown (filtered, sorted, formatted) as a CSV file. */
  protected exportCsv(): void {
    this.grid()?.exportCsv('branches');
  }

  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly branchService = inject(AdminBranchService);
  private readonly notify = inject(NotifyService);
  private readonly confirmation = inject(ConfirmationService);

  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  /** Set when the list failed to load — the grid shows it with Retry (QA DA-15). */
  protected readonly loadError = signal<string | null>(null);
  /** Filters `branches()` client-side (the full list is already loaded) via
   *  `lpg-data-grid`'s built-in quick filter — see its own `searchQuery`
   *  input docstring. */
  protected readonly searchQuery = signal('');
  protected readonly submitting = signal(false);
  protected readonly createDrawerVisible = signal(false);

  protected readonly columns: DataGridColumn<BranchResponse>[] = [
    { field: 'name', header: 'Name', sortable: true, filterable: true },
    { field: 'region', header: 'Region', sortable: true, filterable: true },
    {
      field: 'is_active',
      header: 'Status',
      sortable: true,
      cellRenderer: BranchStatusCell,
    },
    {
      field: 'id',
      header: '',
      valueFormatter: (_value, row) => (row.is_active ? 'Deactivate' : 'Activate'),
      onLinkClick: (row) => this.toggleActive(row),
    },
  ];

  protected readonly form = this.formBuilder.group({
    name: ['', [Validators.required, notBlank, Validators.maxLength(200)]],
    region: [''],
  });

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.branchService.listBranches().subscribe({
      next: (branches) => {
        this.branches.set(branches);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(errorMessageFor(error));
        this.loading.set(false);
      },
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
        this.notify.success(`Branch "${name}" added.`);
        this.createDrawerVisible.set(false);
        this.form.reset();
        this.reload();
      },
      error: () => this.submitting.set(false),
    });
  }

  protected toggleActive(branch: BranchResponse): void {
    if (!branch.is_active) {
      this.setActive(branch, true);
      return;
    }
    this.confirmation.confirm({
      header: 'Deactivate branch?',
      message: `"${branch.name}" will no longer be offered in forms. You can activate it again later.`,
      acceptLabel: 'Deactivate',
      rejectLabel: 'Cancel',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => this.setActive(branch, false),
    });
  }

  private setActive(branch: BranchResponse, nextActive: boolean): void {
    this.branchService.setActive(branch.id, nextActive).subscribe({
      next: () => {
        this.notify.success(`"${branch.name}" ${nextActive ? 'activated' : 'deactivated'}.`);
        this.reload();
      },
    });
  }
}
