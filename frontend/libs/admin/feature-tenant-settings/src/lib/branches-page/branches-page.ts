import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { AdminBranchService, type AppError, type BranchResponse } from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the branch. Please try again.';
  }
}

/** Branch list + create form — `tenant:configure` (`permissionGuard`, route level). */
@Component({
  selector: 'lpg-branches-page',
  standalone: true,
  imports: [ReactiveFormsModule, ButtonDirective, InputText, Message, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <h1>Branches</h1>

      <div class="admin-page__grid">
        <lpg-data-grid
          [rows]="branches()"
          [columns]="columns"
          [loading]="loading()"
          ariaLabel="Branches"
        />
      </div>

      <form class="admin-page__form" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <h2>Add a branch</h2>
        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }
        <div class="admin-page__field">
          <label for="branch-name">Name</label>
          <input pInputText id="branch-name" type="text" formControlName="name" />
        </div>
        <div class="admin-page__field">
          <label for="branch-region">Region (optional)</label>
          <input pInputText id="branch-region" type="text" formControlName="region" />
        </div>
        <button pButton type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Saving…' : 'Add branch' }}
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
export class BranchesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly branchService = inject(AdminBranchService);

  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

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
    const { name, region } = this.form.getRawValue();

    this.branchService.createBranch(name, region || null).subscribe({
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
