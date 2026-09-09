import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  DetailItemComponent,
  DetailListComponent,
  SectionCardComponent,
  formatTimestamp,
  FormFieldComponent,
} from '@lpg/shared/ui';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Tag } from 'primeng/tag';
import {
  LicenseService,
  LicenseStatusStore,
  NotifyService,
  type LicenseLifecycleState,
} from '@lpg/shared/data-access';

const _STATUS_LABELS: Record<LicenseLifecycleState, string> = {
  pending_activation: 'Not activated',
  active: 'Active',
  grace: 'Grace period',
  blocked: 'Blocked',
  revoked: 'Revoked',
};

/** Mirrors `LicenseIssuancePage`'s own `STATUS_SEVERITY` map — the tenant-
 * side status chip should read the same as the platform-side one. */
const _STATUS_SEVERITY: Record<LicenseLifecycleState, 'success' | 'warn' | 'danger'> = {
  pending_activation: 'warn',
  active: 'success',
  grace: 'warn',
  blocked: 'danger',
  revoked: 'danger',
};

/**
 * Tenant-side license activation + status — `agency_admin`,
 * `license:manage_tenant`. The whole route is already gated by this
 * permission, so no further inner RBAC check is needed on the form itself.
 */
@Component({
  selector: 'lpg-license-activation-page',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    FormFieldComponent,
    SectionCardComponent,
    DetailListComponent,
    DetailItemComponent,
    Tag,
  ],
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
            <lpg-form-field label="Activation key" for="license-key" [control]="form.controls.key" [messages]="{ required: 'An activation key is required.' }">
              <input pInputText id="license-key" type="text" formControlName="key" placeholder="LPG-XXXX-XXXX-XXXX-XXXX" [fluid]="true" />
            </lpg-form-field>
            <div class="admin-form-actions">
              <button pButton type="submit" [disabled]="submitting() || form.invalid" [loading]="submitting()">
                Activate
              </button>
            </div>
          </form>
        </section>
      } @else if (status(); as s) {
        <lpg-section-card class="detail-view">
          <lpg-detail-list>
            <lpg-detail-item label="Status">
              <p-tag [value]="statusLabel(s.status)" [severity]="statusSeverity(s.status)" />
            </lpg-detail-item>
            <lpg-detail-item label="Plan">{{ s.planTier ?? '—' }}</lpg-detail-item>
            <lpg-detail-item label="Key">{{ s.keyPrefix ?? '—' }}-****</lpg-detail-item>
            <lpg-detail-item label="Activated">{{ formatTimestamp(s.activatedAt) }}</lpg-detail-item>
            <lpg-detail-item label="Expires">{{ formatTimestamp(s.expiresAt) }}</lpg-detail-item>
            @if (s.status === 'grace') {
              <lpg-detail-item label="Grace period ends">{{ formatTimestamp(s.graceEndsAt) }}</lpg-detail-item>
            }
          </lpg-detail-list>
        </lpg-section-card>
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

      .admin-form-actions {
        display: flex;
        gap: var(--spacing-sm);
        margin-block-start: var(--spacing-sm);
      }

      .detail-view {
        max-inline-size: 480px;
        margin-block-start: var(--spacing-lg);
      }
    `,
  ],
})
export class LicenseActivationPage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly licenseService = inject(LicenseService);
  private readonly licenseStatusStore = inject(LicenseStatusStore);
  private readonly notify = inject(NotifyService);

  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly status = this.licenseStatusStore.status;
  protected readonly statusLabel = (state: LicenseLifecycleState) => _STATUS_LABELS[state];
  protected readonly statusSeverity = (state: LicenseLifecycleState) => _STATUS_SEVERITY[state];
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
        this.notify.success('License activated.');
        this.form.reset();
        this.reload();
      },
      error: () => this.submitting.set(false),
    });
  }
}
