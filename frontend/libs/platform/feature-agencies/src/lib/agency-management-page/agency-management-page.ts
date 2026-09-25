import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Drawer } from 'primeng/drawer';
import { DrawerA11yDirective } from '@lpg/shared/ui';
import { AgencyService, NotifyService, type CreateAgencyResponse } from '@lpg/shared/data-access';
import {
  DataGridComponent,
  FormFieldComponent,
  StatusChipCell,
  type ChipSeverity,
  type DataGridColumn,
  toSentenceCase,
} from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import type { TenantResponse } from '@lpg/shared/data-access';

/** Mirrors `domain/tenant/tenant.py`'s `SLUG_PATTERN` and length bounds. The
 * agency code is also the future subdomain, so it is a lowercase DNS label. */
const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SLUG_MIN_LENGTH = 3;
const SLUG_MAX_LENGTH = 40;

/** "Orient LPG Agency" → "orient-lpg-agency": a starting suggestion for the
 * agency code, which the user can still edit. */
export function suggestAgencyCode(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, SLUG_MAX_LENGTH)
    .replace(/-+$/g, '');
}

/**
 * Platform Console landing page — lists every agency (tenant) with its
 * lifecycle status, plus a detail drawer for Suspend/Reactivate/Close and a
 * Create-agency drawer (agency + its first admin, one-time setup link).
 * `super_admin`, `tenant:manage_platform`, live-checked. Metadata only —
 * never tenant business data (`domain/tenant/tenant.py`'s status
 * transitions: `trial` → `active` → `suspended` ⇄ `active`, `close()`
 * terminal from any of the three).
 */
@Component({
  selector: 'lpg-agency-management-page',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    ButtonDirective,
    Drawer,
    DrawerA11yDirective,
    DataGridComponent,
    ReactiveFormsModule,
    InputText,
    FormFieldComponent,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="admin-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <div class="page-header__text">
            <h1 class="page-title">Agencies</h1>
            <p class="page-subtitle">Every agency (tenant) on this platform.</p>
          </div>
        </ng-template>
      </div>

      <div class="data-toolbar">
        <div class="data-toolbar__filters"></div>
        <div class="data-toolbar__actions">
          <button pButton type="button" (click)="openCreateDrawer()">
            <i class="pi pi-plus"></i><span>Create agency</span>
          </button>
        </div>
      </div>

      @if (!loading() && agencies().length === 0) {
        <div class="empty-state">
          <i class="pi pi-building empty-state__icon"></i>
          <p class="empty-state__title">No agencies yet</p>
        </div>
      } @else {
        <section class="grid-section">
          <lpg-data-grid
            [rows]="agencies()"
            [columns]="columns"
            [loading]="loading()"
            ariaLabel="Agencies"
          />
        </section>
      }

      <!-- Create agency -->
      <p-drawer
        header="Create an agency"
        [(visible)]="createDrawerVisible"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        <form
          id="createAgencyForm"
          [formGroup]="form"
          (ngSubmit)="submit()"
          novalidate
          class="dialog-form"
        >
          <div class="dialog-form__fields">
            <lpg-form-field
              label="Agency name"
              for="agency-name"
              [control]="form.controls.name"
              [messages]="{
                required: 'Agency name is required.',
                maxlength: 'Use at most 120 characters.'
              }"
            >
              <input pInputText id="agency-name" type="text" formControlName="name" [fluid]="true" />
            </lpg-form-field>
            <lpg-form-field
              label="Agency code"
              for="agency-slug"
              [control]="form.controls.slug"
              [messages]="{
                required: 'Agency code is required.',
                minlength: 'Use at least 3 characters.',
                maxlength: 'Use at most 40 characters.',
                pattern:
                  'Lowercase letters, digits and single hyphens only, not starting or ending with a hyphen.'
              }"
            >
              <input
                pInputText
                id="agency-slug"
                type="text"
                formControlName="slug"
                autocapitalize="off"
                autocomplete="off"
                spellcheck="false"
                [fluid]="true"
              />
            </lpg-form-field>
            <lpg-form-field
              label="Primary contact email"
              for="agency-contact-email"
              [control]="form.controls.primaryContactEmail"
              [messages]="{
                required: 'Contact email is required.',
                email: 'Enter a valid email address.'
              }"
            >
              <input
                pInputText
                id="agency-contact-email"
                type="email"
                formControlName="primaryContactEmail"
                [fluid]="true"
              />
            </lpg-form-field>
            <lpg-form-field
              label="First admin email"
              for="agency-admin-email"
              [control]="form.controls.adminEmail"
              [messages]="{
                required: 'Admin email is required.',
                email: 'Enter a valid email address.'
              }"
            >
              <input
                pInputText
                id="agency-admin-email"
                type="email"
                formControlName="adminEmail"
                [fluid]="true"
              />
            </lpg-form-field>
          </div>

          <div class="modal-actions">
            <button pButton type="button" severity="secondary" (click)="createDrawerVisible.set(false)">
              Cancel
            </button>
            <button pButton type="submit" [disabled]="submitting() || form.invalid">
              @if (submitting()) {<i class="pi pi-spin pi-spinner"></i> }Create agency
            </button>
          </div>
        </form>
      </p-drawer>

      <!-- Agency created: one-time setup link -->
      <p-drawer
        header="Agency created"
        [(visible)]="createdDrawerVisible"
        (onHide)="dismissCreated()"
        position="right"
        [modal]="true"
        [closeOnEscape]="true"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        @if (created(); as result) {
          <div class="detail-view">
            <div class="detail-view__fields">
              <div class="detail-item">
                <span class="detail-label">Agency</span>
                <span class="detail-value">{{ result.tenant.name }} ({{ result.tenant.slug }})</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">First admin</span>
                <span class="detail-value">{{ result.admin_email }}</span>
              </div>
              <lpg-form-field label="One-time password setup link" for="agency-setup-link">
                <input
                  pInputText
                  #setupLink
                  id="agency-setup-link"
                  type="text"
                  readonly
                  [value]="setupUrl()"
                  (focus)="setupLink.select()"
                  [fluid]="true"
                />
              </lpg-form-field>
              <p class="detail-value">
                Send this link to the admin. It is shown only once and expires
                {{ expiryLabel() }}. Email delivery is not configured, so nothing was sent.
              </p>
              <p class="detail-value">
                The admin cannot sign in until the agency has an active license —
                <a routerLink="/platform/licenses">issue one next</a>.
              </p>
            </div>

            <div class="modal-actions">
              <button pButton type="button" severity="secondary" (click)="dismissCreated()">Done</button>
              <button pButton type="button" (click)="copySetupLink()">
                <i class="pi pi-copy"></i><span>Copy link</span>
              </button>
            </div>
          </div>
        }
      </p-drawer>

      <p-drawer
        header="Agency Details"
        [(visible)]="showDetailDrawer"
        (onHide)="closeDetails()"
        position="right"
        [modal]="true"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        @if (selectedAgency(); as agency) {
          <div class="detail-view">
            <div class="detail-view__fields">
            <div class="detail-item">
              <span class="detail-label">Name</span>
              <span class="detail-value">{{ agency.name }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Slug</span>
              <span class="detail-value">{{ agency.slug }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Status</span>
              <span class="detail-value">{{ statusLabel(agency.status) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Plan</span>
              <span class="detail-value">{{ agency.subscription_plan }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Primary contact</span>
              <span class="detail-value">{{ agency.primary_contact_email }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Country</span>
              <span class="detail-value">{{ agency.country }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Tenant ID</span>
              <span class="detail-value">{{ agency.id }}</span>
            </div>
            </div>

            <div class="modal-actions">
              <button pButton type="button" severity="secondary" (click)="closeDetails()">Close panel</button>
              @if (agency.status === 'active') {
                <button pButton type="button" severity="warn" [disabled]="acting()" (click)="suspend(agency.id)">
                  @if (acting()) {<i class="pi pi-spin pi-spinner"></i> }Suspend
                </button>
              }
              @if (agency.status === 'suspended') {
                <button pButton type="button" severity="success" [disabled]="acting()" (click)="reactivate(agency.id)">
                  @if (acting()) {<i class="pi pi-spin pi-spinner"></i> }Reactivate
                </button>
              }
              @if (agency.status !== 'closed') {
                <button pButton type="button" severity="danger" [disabled]="acting()" (click)="closeAgency(agency.id)">
                  @if (acting()) {<i class="pi pi-spin pi-spinner"></i> }Close agency
                </button>
              }
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


      .detail-view {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-height: 0;
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

      .modal-actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
      }
    `,
  ],
})
export class AgencyManagementPage implements OnInit {
  private readonly agencyService = inject(AgencyService);
  private readonly notify = inject(NotifyService);
  private readonly formBuilder = inject(NonNullableFormBuilder);

  protected readonly setupLinkInput = viewChild<ElementRef<HTMLInputElement>>('setupLink');

  protected readonly form = this.formBuilder.group({
    name: ['', [Validators.required, Validators.maxLength(120)]],
    slug: [
      '',
      [
        Validators.required,
        Validators.minLength(SLUG_MIN_LENGTH),
        Validators.maxLength(SLUG_MAX_LENGTH),
        Validators.pattern(SLUG_PATTERN),
      ],
    ],
    primaryContactEmail: ['', [Validators.required, Validators.email]],
    adminEmail: ['', [Validators.required, Validators.email]],
  });

  protected readonly createDrawerVisible = signal(false);
  protected readonly createdDrawerVisible = signal(false);
  protected readonly submitting = signal(false);
  protected readonly created = signal<CreateAgencyResponse | null>(null);

  protected readonly loading = signal(false);
  protected readonly acting = signal(false);
  protected readonly agencies = signal<TenantResponse[]>([]);
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedAgency = signal<TenantResponse | null>(null);

  protected readonly statusLabel = (status: string) => toSentenceCase(status);

  /** `domain/tenant/tenant.py`'s lifecycle: `trial` → `active` →
   * `suspended` ⇄ `active`, `close()` terminal from any of the three. */
  private static readonly STATUS_SEVERITY: Record<string, ChipSeverity> = {
    trial: 'info',
    active: 'success',
    suspended: 'danger',
    closed: 'secondary',
  };

  /** Plan tier catalog (`application/license/entitlement.py`):
   * basic/standard/premium, read low-to-high as neutral → better. */
  private static readonly PLAN_SEVERITY: Record<string, ChipSeverity> = {
    basic: 'secondary',
    standard: 'info',
    premium: 'success',
  };

  protected readonly columns: DataGridColumn<TenantResponse>[] = [
    {
      field: 'name',
      header: 'Name',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.openDetails(row),
    },
    { field: 'slug', header: 'Slug', sortable: true },
    {
      field: 'status',
      header: 'Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: AgencyManagementPage.STATUS_SEVERITY },
    },
    {
      field: 'subscription_plan',
      header: 'Plan',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: { severityMap: AgencyManagementPage.PLAN_SEVERITY },
    },
  ];

  ngOnInit(): void {
    this.reload();

    // Suggest an agency code from the name until the user edits the code themselves.
    this.form.controls.name.valueChanges.subscribe((name) => {
      if (this.form.controls.slug.pristine) {
        this.form.controls.slug.setValue(suggestAgencyCode(name), { emitEvent: false });
      }
    });
  }

  private reload(): void {
    this.loading.set(true);
    this.agencyService.listAgencies().subscribe({
      next: (agencies) => {
        this.agencies.set(agencies);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected setupUrl(): string {
    const result = this.created();
    return result ? `${globalThis.location.origin}${result.setup_path}` : '';
  }

  protected expiryLabel(): string {
    const result = this.created();
    return result ? `on ${new Date(result.setup_token_expires_at).toLocaleString()}` : '';
  }

  protected openCreateDrawer(): void {
    this.form.reset();
    this.createDrawerVisible.set(true);
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
    const { name, slug, primaryContactEmail, adminEmail } = this.form.getRawValue();

    this.agencyService
      .create({
        name: name.trim(),
        slug,
        primary_contact_email: primaryContactEmail.trim(),
        admin_email: adminEmail.trim(),
      })
      .subscribe({
        next: (response) => {
          this.submitting.set(false);
          this.createDrawerVisible.set(false);
          this.created.set(response);
          this.createdDrawerVisible.set(true);
          this.notify.success(`Agency "${response.tenant.name}" created.`);
          this.reload();
        },
        error: () => this.submitting.set(false),
      });
  }

  protected async copySetupLink(): Promise<void> {
    try {
      // The Clipboard API only exists on secure origins (HTTPS/localhost).
      await navigator.clipboard.writeText(this.setupUrl());
      this.notify.success('Setup link copied.');
    } catch {
      this.setupLinkInput()?.nativeElement.select();
      this.notify.info('Press Ctrl+C to copy the selected link.');
    }
  }

  protected dismissCreated(): void {
    this.createdDrawerVisible.set(false);
    this.created.set(null);
  }

  protected openDetails(agency: TenantResponse): void {
    this.selectedAgency.set(agency);
    this.showDetailDrawer.set(true);
  }

  protected closeDetails(): void {
    this.showDetailDrawer.set(false);
  }

  protected suspend(tenantId: string): void {
    this.acting.set(true);
    this.agencyService.suspend(tenantId).subscribe({
      next: () => {
        this.acting.set(false);
        this.notify.success('Agency suspended.');
        this.reload();
        this.closeDetails();
      },
      error: () => this.acting.set(false),
    });
  }

  protected reactivate(tenantId: string): void {
    this.acting.set(true);
    this.agencyService.reactivate(tenantId).subscribe({
      next: () => {
        this.acting.set(false);
        this.notify.success('Agency reactivated.');
        this.reload();
        this.closeDetails();
      },
      error: () => this.acting.set(false),
    });
  }

  protected closeAgency(tenantId: string): void {
    this.acting.set(true);
    this.agencyService.close(tenantId).subscribe({
      next: () => {
        this.acting.set(false);
        this.notify.success('Agency closed.');
        this.reload();
        this.closeDetails();
      },
      error: () => this.acting.set(false),
    });
  }
}
