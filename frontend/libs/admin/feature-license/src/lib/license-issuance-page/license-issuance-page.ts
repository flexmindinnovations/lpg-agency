import { HeaderPortalDirective, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Drawer } from 'primeng/drawer';
import { Dialog } from 'primeng/dialog';
import { MessageService } from 'primeng/api';
import {
  LicenseService,
  type AppError,
  type IssuedLicenseResponse,
  type LicenseResponse,
} from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, shortId, toSentenceCase } from '@lpg/shared/ui';

const PLAN_TIERS = ['basic', 'standard', 'premium'] as const;
const APP_TYPES = ['customer_app', 'driver_app', 'warehouse_app'] as const;

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    default:
      return 'Something went wrong. Please try again.';
  }
}

/**
 * Platform-side license management — `super_admin`,
 * `license:manage_platform`, live-checked. The whole route is already
 * gated by this permission, so no further inner RBAC check is needed.
 */
@Component({
  selector: 'lpg-license-issuance-page',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    HeaderPortalDirective,
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Select,
    Drawer,
    Dialog,
    DataGridComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
      <div class="page-header__text">
          <h1 class="page-title">License Issuance</h1>
          <p class="page-subtitle">Issue and manage every tenant's product license.</p>
        </div>
    </ng-template>
        <ng-template lpgHeaderPortal>
  <div class="page-header__actions">
            <button pButton (click)="openIssueDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Issue License</span></button>
          </div>
</ng-template>
      </div>

      @if (!loading() && licenses().length === 0) {
        <div class="empty-state">
          <i class="pi pi-key empty-state__icon"></i>
          <p class="empty-state__title">No licenses issued yet</p>
          <p class="empty-state__description">Issue the first license to get started.</p>
          <button pButton class="mt-4" (click)="openIssueDrawer()"><i pButtonIcon class="pi pi-plus"></i><span pButtonLabel>Issue License</span></button>
        </div>
      } @else {
        <section class="grid-section">
          <div class="grid-wrapper">
            <lpg-data-grid
              [rows]="licenses()"
              [columns]="columns"
              [loading]="loading()"
              ariaLabel="Licenses"
            />
          </div>
        </section>
      }

      <!-- Issue License Drawer -->
      <p-drawer
        [(visible)]="issueDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        header="Issue a license"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form id="issueLicenseForm" [formGroup]="issueForm" (ngSubmit)="issue()" novalidate class="dialog-form">
          <div class="form-group">
            <label for="issue-tenant-id">Tenant ID</label>
            <input pInputText id="issue-tenant-id" type="text" formControlName="tenantId" placeholder="00000000-0000-0000-0000-000000000000" />
            @if (issueForm.controls.tenantId.touched && issueForm.controls.tenantId.invalid) {
              <small class="field-error">Tenant ID is required.</small>
            }
          </div>
          <div class="form-group">
            <label for="issue-plan-tier">Plan tier</label>
            <p-select
              id="issue-plan-tier"
              formControlName="planTier"
              [options]="planTierOptions"
              optionLabel="label"
              optionValue="value"
              appendTo="body">
            </p-select>
          </div>
          <div class="form-group">
            <label for="issue-validity-days">Validity (days)</label>
            <input pInputText id="issue-validity-days" type="number" min="1" formControlName="validityDays" />
          </div>
          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="issueDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || issueForm.invalid" [loading]="submitting()">
              Issue license
            </button>
          </div>
        </form>
      </p-drawer>

      <!-- Shown-once plaintext key dialog -->
      <p-dialog
        [visible]="issuedKey() !== null"
        (visibleChange)="$event ? null : dismissIssuedKey()"
        [modal]="true"
        [closable]="false"
        header="License issued"
        [style]="{ width: '32rem', maxWidth: '100%' }"
      >
        @if (issuedKey(); as issued) {
          <p class="page-lede">
            Copy this key now and share it with the tenant — it will never be shown again.
          </p>
          <div class="issued-key">{{ issued.plaintext_key }}</div>
          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="copyIssuedKey(issued.plaintext_key)">
              <i pButtonIcon class="pi pi-copy"></i>
              <span pButtonLabel>Copy</span>
            </button>
            <button pButton type="button" (click)="dismissIssuedKey()">Done</button>
          </div>
        }
      </p-dialog>

      <!-- Flag Details Drawer -->
      <p-drawer
        header="License Details"
        [visible]="showDetailDrawer()"
        (onHide)="closeDetails()"
        position="right"
        [modal]="true"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        @if (selectedLicense(); as license) {
          <div class="detail-view">
            <div class="detail-item">
              <span class="detail-label">Tenant</span>
              <span class="detail-value">{{ license.tenant_id }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Status</span>
              <span class="detail-value">{{ statusLabel(license.status) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Plan</span>
              <span class="detail-value">{{ license.plan_tier }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Key</span>
              <span class="detail-value">{{ license.key_prefix }}-****</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Issued</span>
              <span class="detail-value">{{ license.issued_at }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Expires</span>
              <span class="detail-value">{{ license.expires_at ?? '—' }}</span>
            </div>

            <form [formGroup]="planTierForm" (ngSubmit)="savePlanTier(license.tenant_id)" class="dialog-form">
              <div class="form-group">
                <label for="detail-plan-tier">Change plan tier</label>
                <p-select
                  id="detail-plan-tier"
                  formControlName="planTier"
                  [options]="planTierOptions"
                  optionLabel="label"
                  optionValue="value"
                  appendTo="body">
                </p-select>
              </div>
              <div class="modal-actions">
                <button pButton type="submit" severity="secondary" [disabled]="savingPlanTier()" [loading]="savingPlanTier()">
                  Save plan tier
                </button>
              </div>
            </form>

            <form [formGroup]="deviceCapForm" (ngSubmit)="saveDeviceCap(license.tenant_id)" class="dialog-form">
              <div class="form-group">
                <label for="detail-app-type">App</label>
                <p-select
                  id="detail-app-type"
                  formControlName="appType"
                  [options]="appTypeOptions"
                  optionLabel="label"
                  optionValue="value"
                  appendTo="body">
                </p-select>
              </div>
              <div class="form-group">
                <label for="detail-max-devices">Device cap (blank = unlimited)</label>
                <input pInputText id="detail-max-devices" type="number" min="0" formControlName="maxDevices" />
              </div>
              <div class="modal-actions">
                <button pButton type="submit" severity="secondary" [disabled]="savingDeviceCap()" [loading]="savingDeviceCap()">
                  Save device cap
                </button>
              </div>
            </form>

            <div class="modal-actions">
              <button pButton type="button" severity="secondary" (click)="closeDetails()">Close</button>
              <button pButton type="button" severity="danger" [disabled]="license.status === 'revoked'" (click)="revoke(license.tenant_id)">
                Revoke license
              </button>
            </div>
          </div>
        }
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

      .grid-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-block-size: 0;
        margin-block-start: var(--spacing-lg);
      }

      .grid-wrapper {
        flex: 1;
        min-block-size: 400px;
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
        overflow: hidden;
      }

      .issued-key {
        font-family: monospace;
        font-size: var(--typography-body-font-size);
        padding: var(--spacing-sm) var(--spacing-md);
        background: var(--color-surface-overlay);
        border-radius: var(--radius-sm);
        word-break: break-all;
        margin-block: var(--spacing-md);
      }

      .detail-view {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        flex: 1;
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
export class LicenseIssuancePage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly licenseService = inject(LicenseService);
  private readonly messageService = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly savingPlanTier = signal(false);
  protected readonly savingDeviceCap = signal(false);
  protected readonly licenses = signal<LicenseResponse[]>([]);
  protected readonly issueDrawerVisible = signal(false);
  protected readonly issuedKey = signal<IssuedLicenseResponse | null>(null);
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedLicense = signal<LicenseResponse | null>(null);

  protected readonly planTierOptions = PLAN_TIERS.map((tier) => ({
    label: toSentenceCase(tier),
    value: tier,
  }));
  protected readonly appTypeOptions = APP_TYPES.map((appType) => ({
    label: toSentenceCase(appType),
    value: appType,
  }));

  protected readonly statusLabel = (status: string) => toSentenceCase(status);

  protected readonly columns: DataGridColumn<LicenseResponse>[] = [
    {
      field: 'tenant_id',
      header: 'Tenant',
      sortable: true,
      filterable: true,
      valueFormatter: (value) => shortId(value),
      tooltipValueGetter: (value) => String(value ?? ''),
      onLinkClick: (row) => this.openDetails(row),
    },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      valueFormatter: (value) => toSentenceCase(String(value)),
    },
    { field: 'plan_tier', header: 'Plan', sortable: true },
    { field: 'key_prefix', header: 'Key' },
    { field: 'issued_at', header: 'Issued', sortable: true },
    { field: 'expires_at', header: 'Expires', sortable: true },
  ];

  protected readonly issueForm = this.formBuilder.group({
    tenantId: ['', [Validators.required]],
    planTier: ['standard', [Validators.required]],
    validityDays: [365, [Validators.required, Validators.min(1)]],
  });

  protected readonly planTierForm = this.formBuilder.group({
    planTier: ['standard', [Validators.required]],
  });

  protected readonly deviceCapForm = this.formBuilder.group({
    appType: ['driver_app', [Validators.required]],
    maxDevices: this.formBuilder.control<number | null>(null),
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.loading.set(true);
    this.licenseService.listLicenses().subscribe({
      next: (licenses) => {
        this.licenses.set(licenses);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected openIssueDrawer(): void {
    this.issueForm.reset({ planTier: 'standard', validityDays: 365 });
    this.issueDrawerVisible.set(true);
  }

  protected issue(): void {
    if (this.submitting()) {
      return;
    }
    if (this.issueForm.invalid) {
      this.issueForm.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    const { tenantId, planTier, validityDays } = this.issueForm.getRawValue();

    this.licenseService.issueLicense(tenantId, planTier, validityDays).subscribe({
      next: (issued) => {
        this.submitting.set(false);
        this.issueDrawerVisible.set(false);
        this.issuedKey.set(issued);
        this.reload();
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected copyIssuedKey(key: string): void {
    void navigator.clipboard.writeText(key);
    this.messageService.add({ severity: 'success', summary: 'Copied', detail: 'Key copied to clipboard.' });
  }

  protected dismissIssuedKey(): void {
    this.issuedKey.set(null);
  }

  protected openDetails(license: LicenseResponse): void {
    this.selectedLicense.set(license);
    this.planTierForm.reset({ planTier: license.plan_tier });
    this.deviceCapForm.reset({ appType: 'driver_app', maxDevices: license.device_caps['driver_app'] ?? null });
    this.showDetailDrawer.set(true);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
  }

  protected savePlanTier(tenantId: string): void {
    if (this.planTierForm.invalid) return;
    this.savingPlanTier.set(true);
    const { planTier } = this.planTierForm.getRawValue();

    this.licenseService.setPlanTier(tenantId, planTier).subscribe({
      next: () => {
        this.savingPlanTier.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Plan tier updated.' });
        this.reload();
        this.closeDetails();
      },
      error: (error: unknown) => {
        this.savingPlanTier.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected saveDeviceCap(tenantId: string): void {
    if (this.deviceCapForm.invalid) return;
    this.savingDeviceCap.set(true);
    const { appType, maxDevices } = this.deviceCapForm.getRawValue();

    this.licenseService.setDeviceCap(tenantId, appType, maxDevices).subscribe({
      next: () => {
        this.savingDeviceCap.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Device cap updated.' });
      },
      error: (error: unknown) => {
        this.savingDeviceCap.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected revoke(tenantId: string): void {
    this.licenseService.revokeLicense(tenantId).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'License revoked.' });
        this.reload();
        this.closeDetails();
      },
      error: (error: unknown) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
