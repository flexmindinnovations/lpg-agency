import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
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

/** Cylinder type list + create form — `tenant:configure`. */
@Component({
  selector: 'lpg-cylinder-types-page',
  standalone: true,
  imports: [ReactiveFormsModule, ButtonDirective, InputText, Message, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <h1>Cylinder Types</h1>

      <div class="admin-page__grid">
        <lpg-data-grid
          [rows]="cylinderTypes()"
          [columns]="columns"
          [loading]="loading()"
          ariaLabel="Cylinder Types"
        />
      </div>

      <form class="admin-page__form" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <h2>Add a cylinder type</h2>
        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }
        <div class="admin-page__field">
          <label for="cylinder-name">Name</label>
          <input pInputText id="cylinder-name" type="text" formControlName="name" />
        </div>
        <div class="admin-page__field">
          <label for="cylinder-weight">Weight (kg)</label>
          <input
            pInputText
            id="cylinder-weight"
            type="number"
            step="0.01"
            formControlName="weightKg"
          />
        </div>
        <button pButton type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Saving…' : 'Add cylinder type' }}
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
export class CylinderTypesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly cylinderTypeService = inject(AdminCylinderTypeService);

  protected readonly cylinderTypes = signal<CylinderTypeResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

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
    const { name, weightKg } = this.form.getRawValue();

    this.cylinderTypeService.createCylinderType(name, weightKg).subscribe({
      next: () => {
        this.submitting.set(false);
        this.form.reset({ weightKg: 0 });
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
