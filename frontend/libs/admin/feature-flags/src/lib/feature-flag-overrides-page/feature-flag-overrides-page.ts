import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';

import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { Select } from 'primeng/select';
import { Message } from 'primeng/message';
import {
  AdminFeatureFlagService,
  type AppError,
  type FeatureFlagSummaryResponse,
} from '@lpg/shared/data-access';

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
  imports: [HeaderTitlePortalDirective, ReactiveFormsModule, ButtonDirective, Select, Message],
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
      <p>Override a platform flag for this tenant only.</p>

      @if (checkedStatus(); as status) {
        <p-message severity="info">{{ status }}</p-message>
      }
      @if (errorMessage(); as message) {
        <p-message severity="error">{{ message }}</p-message>
      }

      @if (!loading() && availableFlags().length === 0) {
        <p-message severity="warn">
          No flags exist yet — a super admin needs to create one on the Platform Flags page first.
        </p-message>
      } @else {
        <section class="admin-form-section">
          <form [formGroup]="form" novalidate>
            <div class="form-group">
              <label for="flag-key">Flag</label>
              <p-select
                id="flag-key"
                formControlName="key"
                [options]="flagOptions()"
                optionLabel="label"
                optionValue="value"
                [loading]="loading()"
                placeholder="Select a flag"
                appendTo="body"
              ></p-select>
            </div>
            <div class="admin-form-actions">
              <button pButton type="button" [disabled]="form.invalid" (click)="checkStatus()">
                Check status
              </button>
              <button
                pButton
                type="button"
                severity="success"
                [disabled]="form.invalid"
                (click)="setOverride(true)"
              >
                Enable for this tenant
              </button>
              <button
                pButton
                type="button"
                severity="danger"
                [disabled]="form.invalid"
                (click)="setOverride(false)"
              >
                Disable for this tenant
              </button>
            </div>
          </form>
        </section>
      }
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
    `,
  ],
})
export class FeatureFlagOverridesPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly featureFlagService = inject(AdminFeatureFlagService);

  protected readonly loading = signal(false);
  protected readonly availableFlags = signal<FeatureFlagSummaryResponse[]>([]);
  protected readonly checkedStatus = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly flagOptions = computed(() =>
    this.availableFlags().map((flag) => ({
      label: `${flag.key} — ${flag.description}`,
      value: flag.key,
    })),
  );

  protected readonly form = this.formBuilder.group({
    key: ['', [Validators.required]],
  });

  ngOnInit(): void {
    this.loading.set(true);
    this.featureFlagService.listAvailableFlags().subscribe({
      next: (flags) => {
        this.availableFlags.set(flags);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

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
