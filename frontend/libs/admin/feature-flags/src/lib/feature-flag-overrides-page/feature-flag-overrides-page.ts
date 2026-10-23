import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { FormFieldComponent, PageHeaderComponent } from '@lpg/shared/ui';

import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
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
  imports: [
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    ReactiveFormsModule,
    ButtonDirective,
    Select,
    Message,
    FormFieldComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <lpg-page-header
            title="Feature Flags"
            subtitle="Turn features on or off for your agency."
          />
        </ng-template>
      </div>
      <p>Override a platform setting for your agency only.</p>

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
            <lpg-form-field label="Flag" for="flag-key" [control]="form.controls.key">
              <p-select
                inputId="flag-key"
                formControlName="key"
                [options]="flagOptions()"
                optionLabel="label"
                optionValue="value"
                [loading]="loading()"
                placeholder="Select a flag"
                appendTo="body"
                [fluid]="true"
              ></p-select>
            </lpg-form-field>
            <div class="admin-form-actions">
              <button
                pButton
                type="button"
                [disabled]="form.invalid || actionLoading()"
                (click)="checkStatus()"
              >
                Check status
              </button>
              @if (isFlagEnabled() === true) {
                <button
                  pButton
                  type="button"
                  severity="danger"
                  [disabled]="form.invalid || actionLoading()"
                  (click)="setOverride(false)"
                >
                  Turn off for your agency
                </button>
              } @else if (isFlagEnabled() === false) {
                <button
                  pButton
                  type="button"
                  severity="success"
                  [disabled]="form.invalid || actionLoading()"
                  (click)="setOverride(true)"
                >
                  Turn on for your agency
                </button>
              }
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

      /* Intro line, status/error/warn messages and the form are stacked
         siblings — without a gap the warn message sat flush against the
         intro text above it. */
      .admin-page {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .admin-form-section {
        inline-size: 100%;
        max-inline-size: none;
      }

      .admin-form-section form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
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
  protected readonly actionLoading = signal(false);
  protected readonly availableFlags = signal<FeatureFlagSummaryResponse[]>([]);
  protected readonly checkedStatus = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly isFlagEnabled = signal<boolean | null>(null);

  protected readonly flagOptions = computed(() =>
    this.availableFlags().map((flag) => ({
      label: `${flag.key} — ${flag.description}`,
      value: flag.key,
    })),
  );

  protected readonly form = this.formBuilder.group({
    key: ['', [Validators.required]],
  });

  constructor() {
    this.form.controls.key.valueChanges.pipe(takeUntilDestroyed()).subscribe((key) => {
      this.errorMessage.set(null);
      if (key) {
        this.checkStatus();
      } else {
        this.isFlagEnabled.set(null);
        this.checkedStatus.set(null);
      }
    });
  }

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
    this.actionLoading.set(true);

    this.featureFlagService.isEnabled(key).subscribe({
      next: (result) => {
        this.actionLoading.set(false);
        this.isFlagEnabled.set(result.enabled);
        this.checkedStatus.set(
          `'${result.key}' is currently ${result.enabled ? 'ON' : 'OFF'} for your tenant.`,
        );
      },
      error: (error: unknown) => {
        this.actionLoading.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }

  protected setOverride(enabled: boolean): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.errorMessage.set(null);
    const { key } = this.form.getRawValue();
    this.actionLoading.set(true);

    this.featureFlagService.setOverride(key, enabled).subscribe({
      next: () => {
        this.actionLoading.set(false);
        this.isFlagEnabled.set(enabled);
        this.checkedStatus.set(`'${key}' is now ${enabled ? 'ON' : 'OFF'} for your tenant.`);
      },
      error: (error: unknown) => {
        this.actionLoading.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
