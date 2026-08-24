import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ButtonDirective } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { MessageService } from 'primeng/api';
import { AgencyService, type AppError } from '@lpg/shared/data-access';
import { DataGridComponent, type DataGridColumn, toSentenceCase } from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import type { TenantResponse } from '@lpg/shared/data-access';

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
 * Platform Console landing page — lists every agency (tenant) with its
 * lifecycle status, plus a detail drawer for Suspend/Reactivate/Close.
 * `super_admin`, `tenant:manage_platform`, live-checked. Metadata only —
 * never tenant business data (`domain/tenant/tenant.py`'s status
 * transitions: `trial` → `active` → `suspended` ⇄ `active`, `close()`
 * terminal from any of the three).
 */
@Component({
  selector: 'lpg-agency-management-page',
  standalone: true,
  imports: [HeaderTitlePortalDirective, ButtonDirective, Drawer, DataGridComponent],
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

      @if (!loading() && agencies().length === 0) {
        <div class="empty-state">
          <i class="pi pi-building empty-state__icon"></i>
          <p class="empty-state__title">No agencies yet</p>
        </div>
      } @else {
        <section class="grid-section">
          <div class="grid-wrapper">
            <lpg-data-grid
              [rows]="agencies()"
              [columns]="columns"
              [loading]="loading()"
              ariaLabel="Agencies"
            />
          </div>
        </section>
      }

      <p-drawer
        header="Agency Details"
        [visible]="showDetailDrawer()"
        (onHide)="closeDetails()"
        position="right"
        [modal]="true"
        styleClass="w-full"
        [style]="{ width: '100%', maxWidth: '32rem' }"
      >
        @if (selectedAgency(); as agency) {
          <div class="detail-view">
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

            <div class="modal-actions">
              <button pButton type="button" severity="secondary" (click)="closeDetails()">Close panel</button>
              @if (agency.status === 'active') {
                <button pButton type="button" severity="warn" [loading]="acting()" (click)="suspend(agency.id)">
                  Suspend
                </button>
              }
              @if (agency.status === 'suspended') {
                <button pButton type="button" severity="success" [loading]="acting()" (click)="reactivate(agency.id)">
                  Reactivate
                </button>
              }
              @if (agency.status !== 'closed') {
                <button pButton type="button" severity="danger" [loading]="acting()" (click)="closeAgency(agency.id)">
                  Close agency
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
  private readonly messageService = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly acting = signal(false);
  protected readonly agencies = signal<TenantResponse[]>([]);
  protected readonly showDetailDrawer = signal(false);
  protected readonly selectedAgency = signal<TenantResponse | null>(null);

  protected readonly statusLabel = (status: string) => toSentenceCase(status);

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
      valueFormatter: (value) => toSentenceCase(String(value)),
    },
    { field: 'subscription_plan', header: 'Plan', sortable: true },
  ];

  ngOnInit(): void {
    this.reload();
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
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Agency suspended.' });
        this.reload();
        this.closeDetails();
      },
      error: (error: unknown) => {
        this.acting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected reactivate(tenantId: string): void {
    this.acting.set(true);
    this.agencyService.reactivate(tenantId).subscribe({
      next: () => {
        this.acting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Agency reactivated.' });
        this.reload();
        this.closeDetails();
      },
      error: (error: unknown) => {
        this.acting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected closeAgency(tenantId: string): void {
    this.acting.set(true);
    this.agencyService.close(tenantId).subscribe({
      next: () => {
        this.acting.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Agency closed.' });
        this.reload();
        this.closeDetails();
      },
      error: (error: unknown) => {
        this.acting.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
