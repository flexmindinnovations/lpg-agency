import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { MultiSelect } from 'primeng/multiselect';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { Dialog } from 'primeng/dialog';
import {
  AgencyService,
  LicenseService,
  NotifyService,
  type IssuedLicenseResponse,
  type LicenseResponse,
  type TenantResponse,
} from '@lpg/shared/data-access';
import {
  DataGridComponent,
  DetailItemComponent,
  DetailListComponent,
  FormFieldComponent,
  StatusChipCell,
  type ChipSeverity,
  type DataGridColumn,
  formatTimestamp,
  toSentenceCase,
} from '@lpg/shared/ui';
import { forkJoin } from 'rxjs';

const PLAN_TIERS = ['basic', 'standard', 'premium'] as const;
const APP_TYPES = ['customer_app', 'driver_app', 'warehouse_app'] as const;
const VALIDITY_OPTIONS = [
  { label: '1 year', value: 365 },
  { label: '2 years', value: 730 },
  { label: '3 years', value: 1095 },
] as const;

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
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    Select,
    MultiSelect,
    Drawer,
    DrawerA11yDirective,
    Dialog,
    DataGridComponent,
    FormFieldComponent,
    DetailListComponent,
    DetailItemComponent,
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
      </div>

      @if (!loading() && licenses().length === 0) {
        <div class="empty-state">
          <i class="pi pi-key empty-state__icon"></i>
          <p class="empty-state__title">No licenses issued yet</p>
          <p class="empty-state__description">Issue the first license to get started.</p>
          <button pButton class="mt-4" (click)="openIssueDrawer()"><i class="pi pi-plus"></i><span>Issue License</span></button>
        </div>
      } @else {
        <div class="data-toolbar">
          <div class="data-toolbar__filters"></div>
          <div class="data-toolbar__actions">
            <button pButton (click)="openIssueDrawer()"><i class="pi pi-plus"></i><span>Issue License</span></button>
          </div>
        </div>
        <section class="grid-section">
          <lpg-data-grid
            [rows]="licenses()"
            [columns]="columns"
            [loading]="loading()"
            ariaLabel="Licenses"
          />
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
          <div class="dialog-form__fields">
          <lpg-form-field label="Tenant" for="issue-tenant-id" [control]="issueForm.controls.tenantId" [messages]="{ required: 'Select a tenant to issue a license for.' }">
            <p-select
              inputId="issue-tenant-id"
              formControlName="tenantId"
              [options]="newOrTrialAgencyOptions()"
              optionLabel="label"
              optionValue="value"
              placeholder="Select a new or trial tenant"
              appendTo="body"
              [fluid]="true"
              (onChange)="onIssueTenantChange($event.value)">
            </p-select>
          </lpg-form-field>

          @if (selectedIssueTenant(); as tenant) {
            <div class="tenant-preview">
              <lpg-detail-item label="Slug">{{ tenant.slug }}</lpg-detail-item>
              <lpg-detail-item label="Plan">{{ tenant.subscription_plan }}</lpg-detail-item>
              <lpg-detail-item label="Primary contact">{{ tenant.primary_contact_email }}</lpg-detail-item>
              <lpg-detail-item label="Country">{{ tenant.country }}</lpg-detail-item>
            </div>
          }

          <lpg-form-field label="Plan tier" for="issue-plan-tier" [control]="issueForm.controls.planTier">
            <p-select
              inputId="issue-plan-tier"
              formControlName="planTier"
              [options]="planTierOptions"
              optionLabel="label"
              optionValue="value"
              appendTo="body"
              [fluid]="true">
            </p-select>
          </lpg-form-field>
          <lpg-form-field label="Validity" for="issue-validity-days" [control]="issueForm.controls.validityDays">
            <p-select
              inputId="issue-validity-days"
              formControlName="validityDays"
              [options]="validityOptions"
              optionLabel="label"
              optionValue="value"
              appendTo="body"
              [fluid]="true">
            </p-select>
          </lpg-form-field>
          </div>
          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="issueDrawerVisible.set(false)">Cancel</button>
            <button pButton type="submit" [disabled]="submitting() || issueForm.invalid">
              @if (submitting()) {<i class="pi pi-spin pi-spinner"></i> }Issue license
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

          @if (activatedLicense(); as activated) {
            <p class="activation-confirmed">
              <i class="pi pi-check-circle"></i>
              Activated — status: {{ statusLabel(activated.status) }}
            </p>
          }

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="copyIssuedKey(issued.plaintext_key)">
              <i class="pi pi-copy"></i>
              <span>Copy</span>
            </button>
            @if (!activatedLicense()) {
              <button pButton type="button" severity="success" [disabled]="activating()" (click)="activateIssuedLicense(issued)">
                @if (activating()) {<i class="pi pi-spin pi-spinner"></i> }Activate license
              </button>
            }
            <button pButton type="button" (click)="dismissIssuedKey()">Done</button>
          </div>
        }
      </p-dialog>

      <!-- Flag Details Drawer -->
      <p-drawer
        header="License Details"
        [(visible)]="showDetailDrawer"
        (onHide)="closeDetails()"
        position="right"
        [modal]="true"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        @if (selectedLicense(); as license) {
          <div class="detail-view">
            <div class="detail-view__fields">
            <lpg-detail-list>
              <lpg-detail-item label="Tenant">{{ license.tenant_name ?? '—' }}</lpg-detail-item>
              <lpg-detail-item label="Tenant ID">{{ license.tenant_id }}</lpg-detail-item>
              <lpg-detail-item label="Status">{{ statusLabel(license.status) }}</lpg-detail-item>
              <lpg-detail-item label="Plan">{{ license.plan_tier }}</lpg-detail-item>
              <lpg-detail-item label="Key">{{ license.key_prefix }}-****</lpg-detail-item>
              <lpg-detail-item label="Issued">{{ formatDate(license.issued_at) }}</lpg-detail-item>
              <lpg-detail-item label="Expires">{{ formatDate(license.expires_at) }}</lpg-detail-item>
            </lpg-detail-list>

            <form [formGroup]="planTierForm" (ngSubmit)="savePlanTier(license.tenant_id)" class="dialog-form dialog-form--inline">
              <div class="dialog-form__fields">
              <lpg-form-field label="Change plan tier" for="detail-plan-tier" [control]="planTierForm.controls.planTier">
                <p-select
                  inputId="detail-plan-tier"
                  formControlName="planTier"
                  [options]="planTierOptions"
                  optionLabel="label"
                  optionValue="value"
                  appendTo="body"
                  [fluid]="true">
                </p-select>
              </lpg-form-field>
              </div>
              <div class="modal-actions">
                <button pButton type="submit" severity="secondary" [disabled]="savingPlanTier()">
                  @if (savingPlanTier()) {<i class="pi pi-spin pi-spinner"></i> }Save plan tier
                </button>
              </div>
            </form>

            <form [formGroup]="deviceCapForm" (ngSubmit)="saveDeviceCap(license.tenant_id)" class="dialog-form dialog-form--inline">
              <div class="dialog-form__fields">
              <!-- p-multiselect is deprecated in favor of p-select [multiple]="true", but
                   Select's #selectedItem template hook only ever exposes a single selected
                   option (findSelectedOptionIndex() returns the first match, even in
                   multiple mode) — there's no supported way to render one chip per selection
                   through it. Reproducing display="chip" would mean hand-rolling the whole
                   closed-box display ourselves, fragile against future PrimeNG internals.
                   Left as-is, same as primeng/chart: deprecated with no equivalent-UX
                   replacement available today. -->
              <lpg-form-field label="Apps" for="detail-app-type" [control]="deviceCapForm.controls.appTypes">
                <p-multiselect
                  inputId="detail-app-type"
                  formControlName="appTypes"
                  [options]="appTypeOptions"
                  optionLabel="label"
                  optionValue="value"
                  display="chip"
                  placeholder="Select apps"
                  appendTo="body"
                  [fluid]="true">
                </p-multiselect>
              </lpg-form-field>
              <lpg-form-field label="Device cap" for="detail-max-devices" [control]="deviceCapForm.controls.maxDevices" hint="Blank = unlimited.">
                <input pInputText id="detail-max-devices" type="number" min="0" formControlName="maxDevices" [fluid]="true" />
              </lpg-form-field>
              </div>
              <div class="modal-actions">
                <button pButton type="submit" severity="secondary" [disabled]="savingDeviceCap()">
                  @if (savingDeviceCap()) {<i class="pi pi-spin pi-spinner"></i> }Save device cap
                </button>
              </div>
            </form>
            </div>

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
        margin-block-start: var(--spacing-lg);
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

      .activation-confirmed {
        display: flex;
        align-items: center;
        gap: var(--spacing-xs);
        color: var(--color-feedback-success, #16a34a);
        font-size: var(--typography-body-small-font-size);
        margin-block-end: var(--spacing-md);
      }

      .tenant-preview {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        padding: var(--spacing-md);
        background: var(--color-surface-overlay);
        border-radius: var(--radius-sm);
        margin-block-end: var(--spacing-md);
      }

      .detail-view {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-height: 0;
      }

      .detail-view__fields {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
      }
    `,
  ],
})
export class LicenseIssuancePage implements OnInit {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly licenseService = inject(LicenseService);
  private readonly agencyService = inject(AgencyService);
  private readonly notify = inject(NotifyService);

  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly savingPlanTier = signal(false);
  protected readonly savingDeviceCap = signal(false);
  protected readonly activating = signal(false);
  protected readonly licenses = signal<LicenseResponse[]>([]);
  protected readonly agencies = signal<TenantResponse[]>([]);
  protected readonly issueDrawerVisible = signal(false);
  protected readonly issuedKey = signal<IssuedLicenseResponse | null>(null);
  protected readonly activatedLicense = signal<LicenseResponse | null>(null);
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedLicense = signal<LicenseResponse | null>(null);
  protected readonly selectedIssueTenant = signal<TenantResponse | null>(null);

  protected readonly planTierOptions = PLAN_TIERS.map((tier) => ({
    label: toSentenceCase(tier),
    value: tier,
  }));
  protected readonly appTypeOptions = APP_TYPES.map((appType) => ({
    label: toSentenceCase(appType),
    value: appType,
  }));
  protected readonly validityOptions = VALIDITY_OPTIONS.map((option) => ({ ...option }));

  /** New/not-yet-onboarded tenants — the natural candidates for a first
   * license (`domain/tenant/tenant.py`'s lifecycle: `trial` is where every
   * tenant starts before a license activates it further). */
  protected readonly newOrTrialAgencyOptions = () =>
    this.agencies()
      .filter((agency) => agency.status === 'trial')
      .map((agency) => ({ label: `${agency.name} (${agency.slug})`, value: agency.id }));

  protected readonly statusLabel = (status: string) => toSentenceCase(status);
  protected readonly formatDate = formatTimestamp;

  /** `domain/license/license.py`'s `LicenseLifecycleState`:
   * pending_activation → active → grace → blocked/revoked. */
  private static readonly STATUS_SEVERITY: Record<string, ChipSeverity> = {
    pending_activation: 'warn',
    active: 'success',
    grace: 'warn',
    blocked: 'danger',
    revoked: 'danger',
  };

  /** Plan tier catalog: basic/standard/premium, read low-to-high as
   * neutral → better — same map used on the Agencies grid. */
  private static readonly PLAN_SEVERITY: Record<string, ChipSeverity> = {
    basic: 'secondary',
    standard: 'info',
    premium: 'success',
  };

  protected readonly columns: DataGridColumn<LicenseResponse>[] = [
    {
      field: 'tenant_name',
      header: 'Tenant',
      sortable: true,
      filterable: true,
      valueFormatter: (value) => String(value ?? '—'),
      onLinkClick: (row) => this.openDetails(row),
    },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: LicenseIssuancePage.STATUS_SEVERITY },
    },
    {
      field: 'plan_tier',
      header: 'Plan',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: LicenseIssuancePage.PLAN_SEVERITY },
    },
    { field: 'key_prefix', header: 'Key' },
    { field: 'issued_at', header: 'Issued', sortable: true, valueFormatter: formatTimestamp },
    { field: 'expires_at', header: 'Expires', sortable: true, valueFormatter: formatTimestamp },
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
    appTypes: this.formBuilder.control<string[]>([]),
    maxDevices: this.formBuilder.control<number | null>(null),
  });

  ngOnInit(): void {
    this.reload();
    this.agencyService.listAgencies().subscribe((agencies) => this.agencies.set(agencies));
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
    this.selectedIssueTenant.set(null);
    this.issueDrawerVisible.set(true);
  }

  protected onIssueTenantChange(tenantId: string): void {
    this.selectedIssueTenant.set(this.agencies().find((agency) => agency.id === tenantId) ?? null);
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
        this.activatedLicense.set(null);
        this.issuedKey.set(issued);
        this.reload();
      },
      error: () => this.submitting.set(false),
    });
  }

  protected copyIssuedKey(key: string): void {
    void navigator.clipboard.writeText(key);
    this.notify.success('Key copied to clipboard.', 'Copied');
  }

  protected activateIssuedLicense(issued: IssuedLicenseResponse): void {
    if (this.activating()) return;
    this.activating.set(true);

    this.licenseService.activateOnBehalfOf(issued.tenant_id, issued.plaintext_key).subscribe({
      next: (activated) => {
        this.activating.set(false);
        this.activatedLicense.set(activated);
        this.notify.success('License activated.');
        this.reload();
      },
      error: () => this.activating.set(false),
    });
  }

  protected dismissIssuedKey(): void {
    this.issuedKey.set(null);
    this.activatedLicense.set(null);
  }

  protected openDetails(license: LicenseResponse): void {
    this.selectedLicense.set(license);
    this.planTierForm.reset({ planTier: license.plan_tier });
    this.deviceCapForm.reset({ appTypes: [], maxDevices: null });
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
        this.notify.success('Plan tier updated.');
        this.reload();
        this.closeDetails();
      },
      error: () => this.savingPlanTier.set(false),
    });
  }

  protected saveDeviceCap(tenantId: string): void {
    if (this.deviceCapForm.invalid) return;
    const { appTypes, maxDevices } = this.deviceCapForm.getRawValue();
    if (appTypes.length === 0) return;

    this.savingDeviceCap.set(true);
    forkJoin(
      appTypes.map((appType) => this.licenseService.setDeviceCap(tenantId, appType, maxDevices)),
    ).subscribe({
      next: () => {
        this.savingDeviceCap.set(false);
        this.notify.success('Device cap updated.');
      },
      error: () => this.savingDeviceCap.set(false),
    });
  }

  protected revoke(tenantId: string): void {
    this.licenseService.revokeLicense(tenantId).subscribe({
      next: () => {
        this.notify.success('License revoked.');
        this.reload();
        this.closeDetails();
      },
    });
  }
}
