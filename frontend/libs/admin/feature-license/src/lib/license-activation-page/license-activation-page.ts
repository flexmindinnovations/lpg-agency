import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { formatTimestamp } from '@lpg/shared/ui';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { MessageService } from 'primeng/api';
import {
  LicenseService,
  LicenseStatusStore,
  type AppError,
  type LicenseLifecycleState,
} from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'LICENSE_ACTIVATION_FAILED':
      return 'That key is invalid, already activated, or has been revoked.';
    default:
      return 'Something went wrong activating the license. Please try again.';
  }
}

const _STATUS_LABELS: Record<LicenseLifecycleState, string> = {
  pending_activation: 'Not activated',
  active: 'Active',
  grace: 'Grace period',
  blocked: 'Blocked',
  revoked: 'Revoked',
};

/**
 * Tenant-side license activation + status — `agency_admin`,
 * `license:manage_tenant`. The whole route is already gated by this
 * permission, so no further inner RBAC check is needed on the form itself.
 */
@Component({
  selector: 'lpg-license-activation-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, ReactiveFormsModule, ButtonDirective, InputText],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">License</h1>
          <p class="page-subtitle">Manage this tenant's product license.</p>
        </div>
    </ng-template>
      </div>

      @if (loading()) {
        <p class="page-lede">Loading license status…</p>
      } @else if (status()?.status === 'pending_activation') {
        <section class="admin-form-section">
          <p class="page-lede">Enter the activation key you received to unlock this tenant.</p>
          <form [formGroup]="form" (ngSubmit)="activate()" novalidate>
            <div class="form-group">
              <label for="license-key">Activation key</label>
              <input pInputText id="license-key" type="text" formControlName="key" placeholder="LPG-XXXX-XXXX-XXXX-XXXX" />
              @if (form.controls.key.touched && form.controls.key.invalid) {
                <small class="field-error">An activation key is required.</small>
              }
            </div>
            <div class="admin-form-actions">
              <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
                Activate
              </button>
            </div>
          </form>
        </section>
      } @else if (status(); as s) {
        <section class="detail-view">
          <div class="detail-item">
            <span class="detail-label">Status</span>
            <span class="detail-value">{{ statusLabel(s.status) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Plan</span>
            <span class="detail-value">{{ s.planTier ?? '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Key</span>
            <span class="detail-value">{{ s.keyPrefix ?? '—' }}-****</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Activated</span>
            <span class="detail-value">{{ formatTimestamp(s.activatedAt) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Expires</span>
            <span class="detail-value">{{ formatTimestamp(s.expiresAt) }}</span>
          </div>
          @if (s.status === 'grace') {
            <div class="detail-item">
              <span class="detail-label">Grace period ends</span>
              <span class="detail-value">{{ formatTimestamp(s.graceEndsAt) }}</span>
            </div>
          }
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
      }

      .detail-view {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        max-inline-size: 480px;
        margin-block-start: var(--spacing-lg);
      }

      .detail-item {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
      }

      .detail-label {
        font-size: var(--typography-caption-font-size);
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .detail-value {
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-primary);
      }
    `,
  ],
})
export class LicenseActivationPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly licenseService = inject(LicenseService);
  private readonly licenseStatusStore = inject(LicenseStatusStore);
  private readonly messageService = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly status = this.licenseStatusStore.status;
  protected readonly statusLabel = (state: LicenseLifecycleState) => _STATUS_LABELS[state];
  protected readonly formatTimestamp = formatTimestamp;

  protected readonly form = this.formBuilder.group({
    key: ['', [Validators.required]],
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.licenseService.getStatus().subscribe({
      next: (response) => {
        this.licenseStatusStore.set({
          status: response.status as LicenseLifecycleState,
          planTier: response.plan_tier,
          keyPrefix: response.key_prefix,
          activatedAt: response.activated_at,
          expiresAt: response.expires_at,
          graceEndsAt: response.grace_ends_at,
        });
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected activate(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    const { key } = this.form.getRawValue();

    this.licenseService.activate(key).subscribe({
      next: () => {
        this.submitting.set(false);
        this.messageService.add({
          severity: 'success',
          summary: 'Success',
          detail: 'License activated.',
        });
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
