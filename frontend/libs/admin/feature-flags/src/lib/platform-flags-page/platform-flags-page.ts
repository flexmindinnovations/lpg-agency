import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import {
  AdminFeatureFlagService,
  type AppError,
  type FeatureFlagResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the flag. Please try again.';
  }
}

/**
 * Platform-wide feature flag management — `feature_flags:manage_platform`,
 * `super_admin` only, live-checked server-side (same high-sensitivity
 * pattern `reconciliation:approve` uses).
 */
@Component({
  selector: 'lpg-platform-flags-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, ReactiveFormsModule, ButtonDirective, InputText, Message, DataGridComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Platform Feature Flags</h1>
          <p class="page-subtitle">Manage platform-wide feature flags and rollout percentages.</p>
        </div>
    </ng-template>
      </div>

      <section class="grid-section">
        <div class="grid-wrapper">
          <lpg-data-grid
            [rows]="flags()"
            [columns]="columns"
            [loading]="loading()"
            ariaLabel="Feature flags"
          />
        </div>
      </section>

      <section class="admin-form-section">
        <h2 class="section-heading">Create a flag</h2>
        <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
          @if (successMessage(); as message) {
            <p-message severity="success">{{ message }}</p-message>
          }
          @if (errorMessage(); as message) {
            <p-message severity="error">{{ message }}</p-message>
          }
          <div class="form-group">
            <label for="flag-key">Key</label>
            <input pInputText id="flag-key" type="text" formControlName="key" />
          </div>
          <div class="form-group">
            <label for="flag-description">Description</label>
            <input pInputText id="flag-description" type="text" formControlName="description" />
          </div>
          <div class="form-group">
            <label for="flag-rollout">Rollout % (optional)</label>
            <input
              pInputText
              id="flag-rollout"
              type="number"
              min="0"
              max="100"
              formControlName="rolloutPercentage"
            />
          </div>
          <div class="admin-form-actions">
            <button pButton type="submit" [disabled]="submitting()">
              {{ submitting() ? 'Creating…' : 'Create flag' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .admin-form-section {
        max-inline-size: 480px;
        margin-block-start: var(--spacing-lg);
      }

      .admin-form-section form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .admin-form-section .form-group {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
      }

      .admin-form-section .form-group label {
        font-weight: var(--typography-label-font-weight);
        font-size: var(--typography-body-small-font-size);
      }

      .admin-form-actions {
        display: flex;
        gap: var(--spacing-sm);
        margin-block-start: var(--spacing-sm);
      }

      .grid-section {
        margin-block-start: var(--spacing-lg);
      }

      .grid-wrapper {
        block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }
    `,
  ],
})
export class PlatformFlagsPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly featureFlagService = inject(AdminFeatureFlagService);

  protected readonly flags = signal<FeatureFlagResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);

  protected readonly columns: DataGridColumn<FeatureFlagResponse>[] = [
    { field: 'key', header: 'Key', sortable: true, filterable: true },
    { field: 'description', header: 'Description' },
    { field: 'is_enabled_by_default', header: 'Default', sortable: true },
    { field: 'rollout_percentage', header: 'Rollout %', numeric: true },
  ];

  protected readonly form = this.formBuilder.group({
    key: ['', [Validators.required]],
    description: ['', [Validators.required]],
    rolloutPercentage: [null as number | null],
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.featureFlagService.listFlags().subscribe({
      next: (flags) => {
        this.flags.set(flags);
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
    this.successMessage.set(null);
    const { key, description, rolloutPercentage } = this.form.getRawValue();

    this.featureFlagService.createFlag(key, description, false, rolloutPercentage).subscribe({
      next: () => {
        this.submitting.set(false);
        this.successMessage.set(`Flag "${key}" created.`);
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
