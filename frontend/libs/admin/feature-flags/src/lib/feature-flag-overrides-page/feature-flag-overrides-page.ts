import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { AdminFeatureFlagService, type AppError } from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong saving the override. Please try again.';
  }
}

/**
 * This tenant's own feature-flag overrides — `feature_flags:manage_tenant`.
 * An explicit override always wins over the platform default/rollout for
 * this tenant (`FeatureFlagService.is_enabled`'s precedence).
 */
@Component({
  selector: 'lpg-feature-flag-overrides-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, ReactiveFormsModule, ButtonDirective, InputText, Message],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">Feature Flags</h1>
          <p class="page-subtitle">Enable or disable feature flags for this tenant.</p>
        </div>
    </ng-template>
      </div>
      <p>Override a platform flag for this tenant only. Blank the key to check a flag's status.</p>

      @if (checkedStatus(); as status) {
        <p-message severity="info">{{ status }}</p-message>
      }
      @if (errorMessage(); as message) {
        <p-message severity="error">{{ message }}</p-message>
      }

      <section class="admin-form-section">
        <form [formGroup]="form" novalidate>
          <div class="form-group">
            <label for="flag-key">Flag key</label>
            <input pInputText id="flag-key" type="text" formControlName="key" />
          </div>
          <div class="admin-form-actions">
            <button pButton type="button" (click)="checkStatus()">Check status</button>
            <button pButton type="button" severity="success" (click)="setOverride(true)">
              Enable for this tenant
            </button>
            <button pButton type="button" severity="danger" (click)="setOverride(false)">
              Disable for this tenant
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
        flex-wrap: wrap;
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
export class FeatureFlagOverridesPage {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly featureFlagService = inject(AdminFeatureFlagService);

  protected readonly checkedStatus = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly form = this.formBuilder.group({
    key: ['', [Validators.required]],
  });

  protected checkStatus(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.errorMessage.set(null);
    const { key } = this.form.getRawValue();

    this.featureFlagService.isEnabled(key).subscribe({
      next: (result) =>
        this.checkedStatus.set(
          `'${result.key}' is currently ${result.enabled ? 'ON' : 'OFF'} for your tenant.`,
        ),
      error: (error: unknown) => this.errorMessage.set(errorMessageFor(error)),
    });
  }

  protected setOverride(enabled: boolean): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.errorMessage.set(null);
    const { key } = this.form.getRawValue();

    this.featureFlagService.setOverride(key, enabled).subscribe({
      next: () =>
        this.checkedStatus.set(`'${key}' is now ${enabled ? 'ON' : 'OFF'} for your tenant.`),
      error: (error: unknown) => this.errorMessage.set(errorMessageFor(error)),
    });
  }
}
